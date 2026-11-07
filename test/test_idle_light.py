# -*- coding: utf-8 -*-
"""Idle-light timeout routing and uplink normalization."""
import asyncio
import json
from os import path

import pytest

# pylint: disable=import-outside-toplevel


def _routes():
    from miot.common import run_control_routes

    async def pause(delay):
        return delay

    return run_control_routes, pause


@pytest.mark.github
def test_route_plan_retries_device_timeout_once():
    """-9999 wakes a sleeping Yeelight; the next try may succeed."""
    from miot.common import (
        ROUTE_FAIL, ROUTE_NEXT, ROUTE_OK, ROUTE_RETRY, control_route_plan)

    assert control_route_plan(0, False) == ROUTE_OK
    assert control_route_plan(1, False) == ROUTE_OK
    assert control_route_plan(-9999, False) == ROUTE_RETRY
    assert control_route_plan(-9999, True) == ROUTE_NEXT
    assert control_route_plan(-704053036, False) == ROUTE_RETRY
    assert control_route_plan(-10006, False) == ROUTE_NEXT
    assert control_route_plan(-4005, False) == ROUTE_FAIL


@pytest.mark.github
def test_sleeping_gateway_falls_through_to_cloud():
    """Gateway -9999 must not block the cloud write Mi Home still uses."""
    run_control_routes, pause = _routes()
    calls = []

    async def gateway():
        calls.append('gateway')
        return -9999

    async def cloud():
        calls.append('cloud')
        return 0

    async def scenario():
        return await run_control_routes(
            [('gateway', gateway), ('cloud', cloud)],
            retry_delay=0,
            sleep=pause)

    ok, rc, route = asyncio.run(scenario())
    assert ok is True
    assert rc == 0
    assert route == 'cloud'
    assert calls == ['gateway', 'gateway', 'cloud']


@pytest.mark.github
def test_local_timeout_skips_retry_and_uses_cloud():
    """A local wait that already expired should not be repeated."""
    run_control_routes, pause = _routes()
    calls = []

    async def gateway():
        calls.append('gateway')
        return -10006

    async def cloud():
        calls.append('cloud')
        return 1

    async def scenario():
        return await run_control_routes(
            [('gateway', gateway), ('cloud', cloud)],
            retry_delay=0,
            sleep=pause)

    ok, rc, route = asyncio.run(scenario())
    assert ok is True
    assert rc == 1
    assert route == 'cloud'
    assert calls == ['gateway', 'cloud']


@pytest.mark.github
def test_property_error_does_not_fall_through():
    """A rejected value stays on the first route."""
    run_control_routes, pause = _routes()
    calls = []

    async def gateway():
        calls.append('gateway')
        return -4005

    async def cloud():
        calls.append('cloud')
        return 0

    async def scenario():
        return await run_control_routes(
            [('gateway', gateway), ('cloud', cloud)],
            retry_delay=0,
            sleep=pause)

    ok, rc, route = asyncio.run(scenario())
    assert ok is False
    assert rc == -4005
    assert route == 'gateway'
    assert calls == ['gateway']


@pytest.mark.github
def test_cloud_uplink_fills_did_from_topic():
    """Cloud pushes omit did; handlers drop the update without it."""
    from miot.common import iter_cloud_uplink, with_did

    topic = 'device/2032272962/up/properties_changed/2/1'
    msg = {'params': [{'siid': 2, 'piid': 1, 'value': True}]}
    changes = iter_cloud_uplink(topic, msg, ('siid', 'piid', 'value'))
    assert changes == [{
        'did': '2032272962', 'siid': 2, 'piid': 1, 'value': True}]
    # The original object is left untouched.
    assert 'did' not in msg['params'][0]

    single = {
        'params': {'did': '2032272962', 'siid': 2, 'piid': 1, 'value': False}
    }
    assert iter_cloud_uplink(
        topic, single, ('siid', 'piid', 'value')) == [single['params']]
    assert iter_cloud_uplink(topic, {'params': {}}, ('value',)) == []
    assert with_did({'siid': 4, 'value': True}, 'lamp')['did'] == 'lamp'


@pytest.mark.github
def test_cloud_shadow_updates_only_when_the_bulb_disagrees():
    """Button and Mi Home changes leave the other side on the old value."""
    from miot.common import same_prop_value, should_push_cloud_shadow

    assert same_prop_value(True, 1)
    assert same_prop_value(False, 0)
    assert not same_prop_value(True, False)
    assert should_push_cloud_shadow(True, False, 0, 100, 60)
    assert not should_push_cloud_shadow(True, True, 0, 100, 60)
    assert not should_push_cloud_shadow(True, 1, 0, 100, 60)
    assert not should_push_cloud_shadow(True, None, 0, 100, 60)
    assert not should_push_cloud_shadow(True, False, 80, 100, 60)
    assert should_push_cloud_shadow(True, False, 30, 100, 60)


@pytest.mark.github
def test_timeout_code_is_translated():
    """-9999 used to surface as an unknown error."""
    i18n_dir = path.normpath(path.join(
        path.dirname(path.abspath(__file__)),
        '../custom_components/xiaomi_home/miot/i18n'))
    seen = 0
    for name in (
            'de', 'en', 'es', 'fr', 'it', 'ja', 'nl', 'pt', 'pt-BR',
            'ru', 'tr', 'zh-Hans', 'zh-Hant'):
        with open(
                path.join(i18n_dir, f'{name}.json'), encoding='utf-8') as fh:
            data = json.load(fh)
        text = data['error']['common']['-9999']
        assert isinstance(text, str) and text
        seen += 1
    assert seen == 13
