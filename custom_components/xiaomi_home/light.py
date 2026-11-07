# -*- coding: utf-8 -*-
"""
Copyright (C) 2024 Xiaomi Corporation.

The ownership and intellectual property rights of Xiaomi Home Assistant
Integration and related Xiaomi cloud service API interface provided under this
license, including source code and object code (collectively, "Licensed Work"),
are owned by Xiaomi. Subject to the terms and conditions of this License, Xiaomi
hereby grants you a personal, limited, non-exclusive, non-transferable,
non-sublicensable, and royalty-free license to reproduce, use, modify, and
distribute the Licensed Work only for your use of Home Assistant for
non-commercial purposes. For the avoidance of doubt, Xiaomi does not authorize
you to use the Licensed Work for any other purpose, including but not limited
to use Licensed Work to develop applications (APP), Web services, and other
forms of software.

You may reproduce and distribute copies of the Licensed Work, with or without
modifications, whether in source or object form, provided that you must give
any other recipients of the Licensed Work a copy of this License and retain all
copyright and disclaimers.

Xiaomi provides the Licensed Work on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied, including, without
limitation, any warranties, undertakes, or conditions of TITLE, NO ERROR OR
OMISSION, CONTINUITY, RELIABILITY, NON-INFRINGEMENT, MERCHANTABILITY, or
FITNESS FOR A PARTICULAR PURPOSE. In any event, you are solely responsible
for any direct, indirect, special, incidental, or consequential damages or
losses arising from the use or inability to use the Licensed Work.

Xiaomi reserves all rights not expressly granted to you in this License.
Except for the rights expressly granted by Xiaomi under this License, Xiaomi
does not authorize you in any form to use the trademarks, copyrights, or other
forms of intellectual property rights of Xiaomi and its affiliates, including,
without limitation, without obtaining other written permission from Xiaomi, you
shall not use "Xiaomi", "Mijia" and other words related to Xiaomi or words that
may make the public associate with Xiaomi in any form to publicize or promote
the software or hardware devices that use the Licensed Work.

Xiaomi has the right to immediately terminate all your authorization under this
License in the event:
1. You assert patent invalidation, litigation, or other claims against patents
or other intellectual property rights of Xiaomi or its affiliates; or,
2. You make, have made, manufacture, sell, or offer to sell products that knock
off Xiaomi or its affiliates' products.

Light entities for Xiaomi Home.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_EFFECT,
    LightEntity,
    LightEntityFeature,
    ColorMode
)
from homeassistant.util.color import (
    value_to_brightness,
    brightness_to_value
)

from .miot.common import (
    direct_write_timeout_ms, miio_result_ok, on_with_bright_level)
from .miot.miot_error import MIoTClientError
from .miot.miot_spec import (
    MIoTSpecAction, MIoTSpecProperty, MIoTSpecService)
from .miot.miot_device import MIoTDevice, MIoTEntityData,  MIoTServiceEntity
from .miot.const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _log_task_error(task: asyncio.Task) -> None:
    """Read a leftover task so a late failure is not lost."""
    if task.cancelled():
        return
    err = task.exception()
    if err:
        _LOGGER.info('ambient turn on task missed, %s', err)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    device_list: list[MIoTDevice] = hass.data[DOMAIN]['devices'][
        config_entry.entry_id]

    new_entities = []
    for miot_device in device_list:
        for data in miot_device.entity_list.get('light', []):
            new_entities.append(
                Light(miot_device=miot_device, entity_data=data))

    if new_entities:
        async_add_entities(new_entities)


class Light(MIoTServiceEntity, LightEntity):
    """Light entities for Xiaomi Home."""
    # pylint: disable=unused-argument
    _VALUE_RANGE_MODE_COUNT_MAX = 30
    _prop_on: Optional[MIoTSpecProperty]
    _prop_brightness: Optional[MIoTSpecProperty]
    _prop_color_temp: Optional[MIoTSpecProperty]
    _prop_color: Optional[MIoTSpecProperty]
    _prop_mode: Optional[MIoTSpecProperty]

    _brightness_scale: Optional[tuple[int, int]]
    _mode_map: Optional[dict[Any, Any]]

    def __init__(
        self, miot_device: MIoTDevice,  entity_data: MIoTEntityData
    ) -> None:
        """Initialize the Light."""
        super().__init__(miot_device=miot_device,  entity_data=entity_data)
        self._attr_color_mode = None
        self._attr_supported_color_modes = set()
        self._attr_supported_features = LightEntityFeature(0)
        if miot_device.did.startswith('group.'):
            self._attr_icon = 'mdi:lightbulb-group'

        self._prop_on = None
        self._prop_brightness = None
        self._prop_color_temp = None
        self._prop_color = None
        self._prop_mode = None
        self._brightness_scale = None
        self._mode_map = None

        # properties
        for prop in entity_data.props:
            # on
            if prop.name == 'on':
                self._prop_on = prop
            # brightness
            if prop.name == 'brightness':
                if prop.value_range:
                    self._brightness_scale = (
                        prop.value_range.min_, prop.value_range.max_)
                    self._prop_brightness = prop
                elif (
                    self._mode_map is None
                    and prop.value_list
                ):
                    # For value-list brightness
                    self._mode_map = prop.value_list.to_map()
                    self._attr_effect_list = list(self._mode_map.values())
                    self._attr_supported_features |= LightEntityFeature.EFFECT
                    self._prop_mode = prop
                else:
                    _LOGGER.info(
                        'invalid brightness format, %s', self.entity_id)
                    continue
            # color-temperature
            if prop.name == 'color-temperature':
                if not prop.value_range:
                    _LOGGER.info(
                        'invalid color-temperature value_range format, %s',
                        self.entity_id)
                    continue
                self._attr_min_color_temp_kelvin = prop.value_range.min_
                self._attr_max_color_temp_kelvin = prop.value_range.max_
                self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._prop_color_temp = prop
            # color
            if prop.name == 'color':
                self._attr_supported_color_modes.add(ColorMode.RGB)
                self._attr_color_mode = ColorMode.RGB
                self._prop_color = prop
            # mode
            if prop.name == 'mode':
                mode_list = None
                if prop.value_list:
                    mode_list = prop.value_list.to_map()
                elif prop.value_range:
                    mode_list = {}
                    if (
                        int((
                            prop.value_range.max_
                            - prop.value_range.min_
                        ) / prop.value_range.step)
                        > self._VALUE_RANGE_MODE_COUNT_MAX
                    ):
                        _LOGGER.error(
                            'too many mode values, %s, %s, %s',
                            self.entity_id, prop.name, prop.value_range)
                    else:
                        for value in range(
                                prop.value_range.min_,
                                prop.value_range.max_,
                                prop.value_range.step):
                            mode_list[value] = f'mode {value}'
                if mode_list:
                    self._mode_map = mode_list
                    self._attr_effect_list = list(self._mode_map.values())
                    self._attr_supported_features |= LightEntityFeature.EFFECT
                    self._prop_mode = prop
                else:
                    _LOGGER.info('invalid mode format, %s', self.entity_id)
                    continue

        if not self._attr_supported_color_modes:
            if self._prop_brightness:
                self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
                self._attr_color_mode = ColorMode.BRIGHTNESS
            elif self._prop_on:
                self._attr_supported_color_modes.add(ColorMode.ONOFF)
                self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> Optional[bool]:
        """Return if the light is on."""
        value_on = self.get_prop_value(prop=self._prop_on)
        # Dirty logic for lumi.gateway.mgl03 indicator light
        if isinstance(value_on, int):
            value_on = value_on == 1
        return value_on

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness."""
        brightness_value = self.get_prop_value(prop=self._prop_brightness)
        if brightness_value is None:
            return None
        return value_to_brightness(self._brightness_scale, brightness_value)

    @property
    def color_temp_kelvin(self) -> Optional[int]:
        """Return the color temperature."""
        return self.get_prop_value(prop=self._prop_color_temp)

    @property
    def rgb_color(self) -> Optional[tuple[int, int, int]]:
        """Return the rgb color value."""
        rgb = self.get_prop_value(prop=self._prop_color)
        if rgb is None:
            return None
        r = (rgb >> 16) & 0xFF
        g = (rgb >> 8) & 0xFF
        b = rgb & 0xFF
        return r, g, b

    @property
    def effect(self) -> Optional[str]:
        """Return the current mode."""
        return self.get_map_value(
            map_=self._mode_map,
            key=self.get_prop_value(prop=self._prop_mode))

    def _is_ambient_light(self) -> bool:
        spec = self.entity_data.spec
        return (
            isinstance(spec, MIoTSpecService)
            and spec.name == 'ambient-light')

    def _on_with_bright_prop(self) -> Optional[MIoTSpecProperty]:
        """Return yeelight.on-with-bright for the main light only.

        That property turns the main lamp on at a brightness. Using it
        for the ambient light turns the main lamp on instead.
        """
        spec = self.entity_data.spec
        if not isinstance(spec, MIoTSpecService) or spec.name != 'light':
            return None
        instance = self.miot_device.spec_instance
        if instance is None:
            return None
        for service in instance.services:
            for prop in service.properties:
                if prop.name == 'on-with-bright' and prop.writable:
                    return prop
        return None

    def _on_with_bright_level(
        self, prop: MIoTSpecProperty, kwargs: dict
    ) -> int:
        requested = None
        if ATTR_BRIGHTNESS in kwargs and self._brightness_scale:
            requested = brightness_to_value(
                self._brightness_scale, kwargs[ATTR_BRIGHTNESS])
        current = self.get_prop_value(prop=self._prop_brightness)
        if prop.value_range:
            minimum = int(prop.value_range.min_)
            maximum = int(prop.value_range.max_)
        else:
            minimum, maximum = 1, 100
        return on_with_bright_level(
            requested, current, minimum, maximum)

    async def _cloud_on_with_bright(self, level: int) -> bool:
        prop = self._on_with_bright_prop()
        if prop is None:
            return False
        try:
            return await self.miot_device.miot_client.set_prop_async(
                did=self.miot_device.did,
                siid=prop.service.iid,
                piid=prop.iid,
                value=level)
        except MIoTClientError as err:
            _LOGGER.info(
                'on-with-bright missed, %s, %s', self.entity_id, err)
            return False

    def _ambient_toggle(self) -> Optional[MIoTSpecAction]:
        spec = self.entity_data.spec
        if not isinstance(spec, MIoTSpecService):
            return None
        for action in spec.actions:
            if action.name == 'toggle':
                return action
        return None

    async def _call_miio(self, method: str, params: list) -> bool:
        """Send one legacy Yeelight method to the lamp IP."""
        try:
            reply = await self.miot_device.miot_client.call_yeelight_async(
                did=self.miot_device.did,
                method=method,
                params=params,
                timeout_ms=direct_write_timeout_ms(),
                retry_count=1)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.info(
                '%s missed, %s, %s', method, self.entity_id, err)
            return False
        _LOGGER.info('%s reply, %s, %s', method, self.entity_id, reply)
        return miio_result_ok(reply)

    def _remember_ambient(self, on: bool, level: Optional[int]) -> None:
        if not self._prop_on:
            return
        value_on: Any = on if self._prop_on.format_ == bool else int(on)
        self.set_prop_value(self._prop_on, value_on)
        if level is not None and self._prop_brightness:
            self.set_prop_value(self._prop_brightness, level)

    async def _bg_power(self, on: bool) -> bool:
        """Turn only the fill light on or off.

        Integer 1 is accepted and then ignored. ``on=true`` is a cloud
        property value error. ``bg_set_power`` is the Yeelight command
        for the background channel and does not switch the main lamp.
        """
        power = 'on' if on else 'off'
        return await self._call_miio(
            'bg_set_power', [power, 'sudden', 0])

    async def _turn_on_ambient(self, **kwargs) -> Optional[bool]:
        """Turn the fill light on.

        Returns whether brightness was written, or None when no command
        was accepted.
        """
        if not self._prop_on:
            return None
        level = self._on_with_bright_level(
            self._prop_brightness or self._prop_on, kwargs)
        client = self.miot_device.miot_client
        bg_task = asyncio.create_task(self._bg_power(True))
        direct_task = asyncio.create_task(
            client.set_prop_direct_only_async(
                did=self.miot_device.did,
                siid=self._prop_on.service.iid,
                piid=self._prop_on.iid,
                value=True))
        pending = {bg_task, direct_task}
        bg_ok = False
        direct_ok = False
        while pending and not (bg_ok or direct_ok):
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    ok = bool(task.result())
                except Exception:  # pylint: disable=broad-exception-caught
                    ok = False
                if task is bg_task:
                    bg_ok = ok
                else:
                    direct_ok = ok
        for task in pending:
            task.add_done_callback(_log_task_error)
        if bg_ok:
            wrote_level = None
            if ATTR_BRIGHTNESS in kwargs:
                if await self._call_miio(
                        'bg_set_bright', [int(level), 'sudden', 0]):
                    wrote_level = int(level)
            self._remember_ambient(True, wrote_level)
            return wrote_level is not None
        if direct_ok:
            self._remember_ambient(True, None)
            return False
        toggle = self._ambient_toggle()
        if toggle is not None and await client.try_cloud_action_async(
                did=self.miot_device.did,
                siid=toggle.service.iid,
                aiid=toggle.iid):
            self._remember_ambient(True, None)
            return False
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on.

        Shall set attributes in kwargs if applicable.
        """
        # lamp39 rejects cloud light.on=true with "property value error".
        # on-with-bright is the turn-on the firmware accepts, and it has
        # to go to cloud without a gateway request in front of it.
        wrote_on = False
        wrote_brightness = False
        on_with_bright = self._on_with_bright_prop()
        if self._prop_on and on_with_bright is not None:
            level = self._on_with_bright_level(on_with_bright, kwargs)
            if await self._cloud_on_with_bright(level):
                value_on = True if self._prop_on.format_ == bool else 1
                self.set_prop_value(self._prop_on, value_on)
                if self._prop_brightness:
                    self.set_prop_value(self._prop_brightness, level)
                wrote_on = True
                wrote_brightness = True
        if self._prop_on and not wrote_on and self._is_ambient_light():
            ambient_wrote = await self._turn_on_ambient(**kwargs)
            if ambient_wrote is None:
                raise MIoTClientError(
                    f'ambient turn on missed, {self.entity_id}')
            wrote_on = True
            wrote_brightness = ambient_wrote
        # on
        # Dirty logic for lumi.gateway.mgl03 indicator light
        if self._prop_on and not wrote_on:
            value_on = True if self._prop_on.format_ == bool else 1
            await self.set_property_async(
                prop=self._prop_on, value=value_on)
        # brightness
        if ATTR_BRIGHTNESS in kwargs and not wrote_brightness:
            brightness = brightness_to_value(
                self._brightness_scale, kwargs[ATTR_BRIGHTNESS])
            await self.set_property_async(
                prop=self._prop_brightness, value=brightness,
                write_ha_state=False)
        # color-temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            await self.set_property_async(
                prop=self._prop_color_temp,
                value=kwargs[ATTR_COLOR_TEMP_KELVIN],
                write_ha_state=False)
            self._attr_color_mode = ColorMode.COLOR_TEMP
        # rgb color
        if ATTR_RGB_COLOR in kwargs:
            r = kwargs[ATTR_RGB_COLOR][0]
            g = kwargs[ATTR_RGB_COLOR][1]
            b = kwargs[ATTR_RGB_COLOR][2]
            rgb = (r << 16) | (g << 8) | b
            await self.set_property_async(
                prop=self._prop_color, value=rgb,
                write_ha_state=False)
            self._attr_color_mode = ColorMode.RGB
        # mode
        if ATTR_EFFECT in kwargs:
            await self.set_property_async(
                prop=self._prop_mode,
                value=self.get_map_key(
                    map_=self._mode_map, value=kwargs[ATTR_EFFECT]),
                write_ha_state=False)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        if not self._prop_on:
            return
        if self._is_ambient_light() and await self._bg_power(False):
            self._remember_ambient(False, None)
            self.async_write_ha_state()
            return
        # Dirty logic for lumi.gateway.mgl03 indicator light
        value_on = False if self._prop_on.format_ == bool else 0
        await self.set_property_async(prop=self._prop_on, value=value_on)
