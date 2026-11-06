# -*- coding: utf-8 -*-
"""Unit test for Yeelight on-with-bright turn-on helpers."""
import pytest

# pylint: disable=import-outside-toplevel


def _base_spec(iid: int, type_: str, name: str) -> dict:
    return {
        'type': type_,
        'name': name,
        'iid': iid,
        'description': name,
        'description_trans': name,
        'proprietary': False,
        'need_filter': False,
        'format': 'bool',
        'access': ['read', 'write', 'notify'],
        'unit': None,
        'value_range': None,
        'value_list': None,
        'precision': 0,
        'expr': None,
        'icon': None
    }


def _lamp39_spec() -> dict:
    light_on = _base_spec(
        1, 'urn:miot-spec-v2:property:on:00000006:yeelink-lamp39:1', 'on')
    brightness = _base_spec(
        2,
        'urn:miot-spec-v2:property:brightness:0000000D:yeelink-lamp39:1',
        'brightness')
    brightness['format'] = 'int'
    brightness['unit'] = 'percentage'
    brightness['value_range'] = {'min': 1, 'max': 100, 'step': 1}
    on_with_bright = _base_spec(
        1,
        'urn:yeelink-spec:property:on-with-bright:00000001:yeelink-lamp39:1',
        'on-with-bright')
    on_with_bright['format'] = 'int'
    on_with_bright['access'] = ['write']
    on_with_bright['unit'] = 'percentage'
    on_with_bright['value_range'] = {'min': 1, 'max': 100, 'step': 1}
    ambient_on = _base_spec(
        1, 'urn:miot-spec-v2:property:on:00000006:yeelink-lamp39:1', 'on')
    return {
        'urn': 'urn:miot-spec-v2:device:light:0000A001:yeelink-lamp39:1',
        'name': 'light',
        'description': 'yeelink light lamp39',
        'description_trans': 'light',
        'services': [
            {
                'type': (
                    'urn:miot-spec-v2:service:light:00007802:'
                    'yeelink-lamp39:1'),
                'name': 'light',
                'iid': 2,
                'description': 'Light',
                'description_trans': 'Light',
                'proprietary': False,
                'need_filter': False,
                'properties': [light_on, brightness],
                'events': [],
                'actions': []
            },
            {
                'type': (
                    'urn:miot-spec-v2:service:ambient-light:0000789D:'
                    'yeelink-lamp39:1'),
                'name': 'ambient-light',
                'iid': 4,
                'description': 'Ambient Light',
                'description_trans': 'Ambient Light',
                'proprietary': False,
                'need_filter': False,
                'properties': [ambient_on],
                'events': [],
                'actions': []
            },
            {
                'type': (
                    'urn:yeelink-spec:service:yeelight:00007801:'
                    'yeelink-lamp39:1'),
                'name': 'yeelight',
                'iid': 5,
                'description': 'yeelight',
                'description_trans': 'yeelight',
                'proprietary': True,
                'need_filter': False,
                'properties': [on_with_bright],
                'events': [],
                'actions': []
            }
        ]
    }


class _Entity:
    def __init__(self, spec, props=None):
        self.spec = spec
        self.props = set(props or [])


@pytest.mark.github
def test_brightness_for_on_with_bright():
    from miot.common import brightness_for_on_with_bright

    assert brightness_for_on_with_bright(40, 10, 1, 100) == 40
    assert brightness_for_on_with_bright(None, 55, 1, 100) == 55
    assert brightness_for_on_with_bright(None, None, 1, 100) == 1
    assert brightness_for_on_with_bright(None, None, None, None) == 1
    assert brightness_for_on_with_bright(0, 80, 1, 100) == 1
    assert brightness_for_on_with_bright(200, None, 1, 100) == 100


@pytest.mark.github
def test_attach_on_with_bright_to_main_light_only():
    from miot.common import (
        attach_on_with_bright_to_lights, find_on_with_bright_prop)
    from miot.miot_spec import MIoTSpecInstance

    spec = MIoTSpecInstance.load(_lamp39_spec())
    prop = find_on_with_bright_prop(spec)
    assert prop is not None
    assert prop.name == 'on-with-bright'
    assert prop.writable
    assert prop.iid == 1
    assert prop.service.iid == 5

    main_light = None
    ambient = None
    for service in spec.services:
        if service.name == 'light':
            main_light = _Entity(service, list(service.properties))
        elif service.name == 'ambient-light':
            ambient = _Entity(service, list(service.properties))
    entity_list = {'light': [main_light, ambient]}
    attach_on_with_bright_to_lights(spec, entity_list)

    assert prop.platform == 'light'
    assert prop in main_light.props
    assert prop not in ambient.props
    assert find_on_with_bright_prop(spec) is prop
