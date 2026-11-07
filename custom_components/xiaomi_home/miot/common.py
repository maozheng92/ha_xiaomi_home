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

Common utilities.
"""
import asyncio
import json
from os import path
import random
from typing import Any, Optional
import hashlib
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from paho.mqtt.matcher import MQTTMatcher
import yaml
from slugify import slugify

MIOT_ROOT_PATH: str = path.dirname(path.abspath(__file__))


def gen_absolute_path(relative_path: str) -> str:
    """Generate an absolute path."""
    return path.join(MIOT_ROOT_PATH, relative_path)


def calc_group_id(uid: str, home_id: str) -> str:
    """Calculate the group ID based on a user ID and a home ID."""
    return hashlib.sha1(
        f'{uid}central_service{home_id}'.encode('utf-8')).hexdigest()[:16]


def load_json_file(json_file: str) -> dict:
    """Load a JSON file."""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_yaml_file(yaml_file: str) -> dict:
    """Load a YAML file."""
    with open(yaml_file, 'r', encoding='utf-8') as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def randomize_int(value: int, ratio: float) -> int:
    """Randomize an integer value."""
    return int(value * (1 - ratio + random.random()*2*ratio))


def randomize_float(value: float, ratio: float) -> float:
    """Randomize a float value."""
    return value * (1 - ratio + random.random()*2*ratio)


def slugify_name(name: str, separator: str = '_') -> str:
    """Slugify a name."""
    return slugify(name, separator=separator)


def slugify_did(cloud_server: str, did: str) -> str:
    """Slugify a device id."""
    return slugify(f'{cloud_server}_{did}', separator='_')


# Awake gateway writes usually return within this window. An idle
# Yeelight does not: the hub waits out "user ack timeout" first.
LOCAL_WRITE_GRACE_SEC = 0.4


def local_write_needs_cloud(rc: Optional[int]) -> bool:
    """Return True when a local write should be retried in the cloud.

    -9999 is the device reply "user ack timeout". yeelink.light.lamp39
    returns it through the central gateway after the lamp has been idle.
    -10006 is the gateway request timeout for the same case.
    -4002 is "property not writable". hotata.airer.d10zm returns it for
    light brightness when a second local write overlaps the first, and
    also when the gateway cannot apply a write that cloud still accepts.
    """
    return rc in (-9999, -10006, -4002)


def local_write_grace_sec() -> float:
    """Return how long a local write may block before cloud starts."""
    return LOCAL_WRITE_GRACE_SEC


def should_start_cloud_write(
    local_finished: bool, rc: Optional[int]
) -> bool:
    """Return True when cloud should run alongside or after local.

    A fast local success stays local. If the device is still silent, or
    it already returned an ack timeout, cloud has to start. Waiting for
    the whole gateway timeout is what leaves the lamp dark after press.
    """
    if not local_finished:
        return True
    if rc in (0, 1):
        return False
    if rc is None:
        return True
    return local_write_needs_cloud(rc)


def cloud_value_rejected(rc: Optional[int]) -> bool:
    """Return True when the value itself was rejected.

    -704220043 and -706012043 are Xiaomi cloud "property value error".
    -4005 is the same rejection from the device. yeelink.light.lamp39
    returns it for ``light.on=true``. The turn-on it accepts is the
    write-only ``yeelight.on-with-bright`` value, 1 to 100.
    """
    return rc in (-704220043, -706012043, -4005)


def on_with_bright_level(
    requested: Optional[float],
    current: Optional[float],
    minimum: int,
    maximum: int,
) -> int:
    """Pick a legal on-with-bright value.

    A requested brightness wins. Otherwise keep the lamp's last level.
    With neither, use the top of the range.
    """
    level = requested if requested is not None else current
    if level is None:
        level = maximum
    value = int(round(float(level)))
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def prefers_cloud_write(model: Optional[str]) -> bool:
    """Return True when a write should skip the local route.

    yeelink.light.* sleeps its Wi-Fi link. A central-gateway write then
    sits in "user ack timeout" (-9999) for several seconds, and a cloud
    write started beside it still waits behind that attempt. al-one/
    hass-xiaomi-miot does not do that: ``miot_cloud_write`` and a failed
    local state send ``set_properties`` to Xiaomi cloud only, and Yeelight
    local mode talks to the lamp with ``set_power`` instead of the hub.
    These models have no direct ``set_power`` path here, so the matching
    behaviour is a cloud write with no gateway request in front of it.
    """
    return bool(model and model.startswith('yeelink.light.'))


class MIoTMatcher(MQTTMatcher):
    """MIoT Pub/Sub topic matcher."""

    def iter_all_nodes(self) -> Any:
        """Return an iterator on all nodes with their paths and contents."""
        def rec(node, path_):
            # pylint: disable=protected-access
            if node._content:
                yield ('/'.join(path_), node._content)
            for part, child in node._children.items():
                yield from rec(child, path_ + [part])
        return rec(self._root, [])

    def get(self, topic: str) -> Optional[Any]:
        try:
            return self[topic]
        except KeyError:
            return None


class MIoTHttp:
    """MIoT Common HTTP API."""
    @staticmethod
    def get(
        url: str, params: Optional[dict] = None, headers: Optional[dict] = None
    ) -> Optional[str]:
        full_url = url
        if params:
            encoded_params = urlencode(params)
            full_url = f'{url}?{encoded_params}'
        request = Request(full_url, method='GET', headers=headers or {})
        content: Optional[bytes] = None
        with urlopen(request) as response:
            content = response.read()
        return str(content, 'utf-8') if content else None

    @staticmethod
    def get_json(
        url: str, params: Optional[dict] = None, headers: Optional[dict] = None
    ) -> Optional[dict]:
        response = MIoTHttp.get(url, params, headers)
        return json.loads(response) if response else None

    @staticmethod
    def post(
        url: str, data: Optional[dict] = None, headers: Optional[dict] = None
    ) -> Optional[str]:
        pass

    @staticmethod
    def post_json(
        url: str, data: Optional[dict] = None, headers: Optional[dict] = None
    ) -> Optional[dict]:
        response = MIoTHttp.post(url, data, headers)
        return json.loads(response) if response else None

    @staticmethod
    async def get_async(
        url: str, params: Optional[dict] = None, headers: Optional[dict] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> Optional[str]:
        # TODO: Use aiohttp
        ev_loop = loop or asyncio.get_running_loop()
        return await ev_loop.run_in_executor(
            None, MIoTHttp.get, url, params, headers)

    @staticmethod
    async def get_json_async(
        url: str, params: Optional[dict] = None, headers: Optional[dict] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> Optional[dict]:
        ev_loop = loop or asyncio.get_running_loop()
        return await ev_loop.run_in_executor(
            None, MIoTHttp.get_json, url, params, headers)

    @ staticmethod
    async def post_async(
        url: str, data: Optional[dict] = None, headers: Optional[dict] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> Optional[str]:
        ev_loop = loop or asyncio.get_running_loop()
        return await ev_loop.run_in_executor(
            None, MIoTHttp.post, url, data, headers)


async def get_system_info_str(hass) -> str:
    """Get system info string for User-Agent."""
    # pylint: disable=import-outside-toplevel
    from homeassistant.helpers.system_info import async_get_system_info
    info = await async_get_system_info(hass)
    version = info['version']
    os_name = info['os_name']
    os_version = info['os_version']
    arch = info['arch']
    installation_type = info['installation_type']
    return (
        f'hass/{version} ({os_name}/{os_version};'
        f' {arch}; {installation_type})'
    )
