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
from typing import Any, Callable, Optional
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


def entity_uses_native_temperature(entity_cls: type) -> bool:
    """Return whether the entity class reads native temperature members.

    Home Assistant 2026.11 renamed the climate and water heater temperature
    members. A core that defines ``native_temperature_unit`` reads those
    names and reports integrations that still provide the previous ones.
    """
    return any(
        'native_temperature_unit' in vars(klass)
        for klass in entity_cls.__mro__)


def lookup_device_entry(
    registry: Any, identifier: tuple[str, str], config_entry_id: str
) -> Any:
    """Look up a device entry owned by one config entry.

    Home Assistant 2026.8 makes device identifiers unique per config entry.
    ``async_get_device`` is deprecated because that lookup is ambiguous, and
    it stops working in 2027.8. Use ``async_get_device_by_identifier`` when
    the registry provides it. Older registries still key devices by identifier
    alone.
    """
    get_by_identifier = getattr(
        registry, 'async_get_device_by_identifier', None)
    if get_by_identifier is not None:
        return get_by_identifier(identifier, config_entry_id)
    return registry.async_get_device(
        identifiers={identifier}, connections=None)


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


# The device, or the route waiting on it, did not answer in time.
# Another route can still deliver the same write.
ROUTE_TIMEOUT_CODES = frozenset({
    -9999, -10006, -704053036, -704083036,
})
# A light that has been off for a long time drops the first command and
# stays off. The same route accepts the next one. -10006 already waited
# out the local timer, so that code changes route immediately.
SOFT_DEVICE_TIMEOUT_CODES = frozenset({
    -9999, -704053036, -704083036,
})
ROUTE_OK = 'ok'
ROUTE_RETRY = 'retry'
ROUTE_NEXT = 'next'
ROUTE_FAIL = 'fail'


def control_route_plan(rc: int, retried: bool) -> str:
    """Choose ok, retry, next route, or fail for a control result."""
    if rc in (0, 1):
        return ROUTE_OK
    if not retried and rc in SOFT_DEVICE_TIMEOUT_CODES:
        return ROUTE_RETRY
    if rc in ROUTE_TIMEOUT_CODES:
        return ROUTE_NEXT
    return ROUTE_FAIL


async def run_control_routes(
    routes: list,
    retry_delay: float = 1.0,
    sleep: Optional[Callable] = None,
    on_plan: Optional[Callable] = None,
) -> tuple[bool, Optional[int], Optional[str]]:
    """Try gateway, then LAN, then cloud, until one accepts the command.

    Each route is ``(name, async_call)``. ``async_call`` returns the
    device code, or None when that route produced no code. Returns
    ``(True, code, route)`` on success. Returns ``(False, code, route)``
    when a route failed for a reason other than a timeout. Returns
    ``(False, code, None)`` when every route timed out. ``code`` is
    None when no route reported one.
    """
    pause: Callable = sleep or asyncio.sleep
    last_rc: Optional[int] = None
    for name, call in routes:
        retried = False
        while True:
            rc = await call()
            if not isinstance(rc, int):
                break
            plan = control_route_plan(rc, retried)
            if on_plan and plan != ROUTE_OK:
                on_plan(name, rc, plan)
            if plan == ROUTE_OK:
                return True, rc, name
            last_rc = rc
            if plan == ROUTE_RETRY:
                retried = True
                await pause(retry_delay)
                continue
            if plan == ROUTE_FAIL:
                return False, rc, name
            break
    return False, last_rc, None


def same_prop_value(left: Any, right: Any) -> bool:
    """Compare property values, treating 0/1 and False/True as the same."""
    if left == right:
        return True
    if isinstance(left, bool) or isinstance(right, bool):
        if isinstance(left, (bool, int)) and isinstance(right, (bool, int)):
            if not isinstance(left, bool):
                left = bool(left)
            if not isinstance(right, bool):
                right = bool(right)
            return left == right
    return False


def gateway_get_properties_rpc(
    did: str, siid: int, piid: int, rpc_id: int
) -> dict:
    """Build the RPC that makes the gateway read the device.

    ``proxy/get`` returns the gateway cache. ``get_properties`` is sent
    to the device, so the gateway can replace that cached value.
    """
    return {
        'did': did,
        'rpc': {
            'id': rpc_id,
            'method': 'get_properties',
            'params': [{
                'did': did,
                'siid': siid,
                'piid': piid,
            }],
        },
    }


def gateway_rpc_prop_value(did: str, result: Any) -> Any:
    """Return the value from one gateway ``get_properties`` result."""
    if not isinstance(result, dict):
        return None
    rows = result.get('result')
    if not isinstance(rows, list) or len(rows) != 1:
        return None
    row = rows[0]
    if not isinstance(row, dict) or row.get('did') != did:
        return None
    if row.get('code', 0) not in (0, 1) or 'value' not in row:
        return None
    return row.get('value')


def command_still_holds(
    commanded: Any, until: float, value: Any, now: float
) -> bool:
    """Whether a read must not replace a command that is still settling.

    After a long off, the first successful on often arrives through the
    cloud. The gateway cache still answers ``false``. Publishing that
    value, or writing it back to the cloud, turns the bulb off again.
    """
    if now >= until:
        return False
    return not same_prop_value(commanded, value)


def should_push_cloud_shadow(
    live: Any, shadow: Any, fail_at: float, now: float, backoff: float
) -> bool:
    """The cloud shadow is what Mi Home shows when the bulb stops reporting.

    Push the live value only when a device read and the cloud cache
    disagree. A missing cache read is not a disagreement.
    """
    if live is None or shadow is None:
        return False
    if same_prop_value(live, shadow):
        return False
    if fail_at and now - fail_at < backoff:
        return False
    return True


def did_from_device_topic(topic: str) -> Optional[str]:
    """Return the did encoded in ``device/{did}/up/...``."""
    parts = str(topic).split('/')
    if len(parts) >= 2 and parts[0] == 'device' and parts[1]:
        return parts[1]
    return None


def with_did(params: dict, did: Optional[str]) -> dict:
    """Copy a property or event payload and fill a missing did."""
    if did and isinstance(params, dict) and 'did' not in params:
        return {**params, 'did': did}
    return params


def iter_cloud_uplink(
    topic: str, msg: Any, required: tuple
) -> list[dict]:
    """Normalize one cloud properties_changed or event_occured message.

    ``params`` is either one object or a list of objects. The did is in
    the topic when an object does not repeat it. Handlers match
    subscriptions by did, so a missing did drops the update and the
    entity keeps a stale state.
    """
    if not isinstance(msg, dict):
        return []
    raw = msg.get('params', None)
    if isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, list):
        items = [item for item in raw if isinstance(item, dict)]
    else:
        return []
    did = did_from_device_topic(topic)
    changes = []
    for item in items:
        if any(key not in item for key in required):
            continue
        changes.append(with_did(item, did))
    return changes
