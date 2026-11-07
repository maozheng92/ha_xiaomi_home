# -*- coding: utf-8 -*-
"""Unit test for local write cloud fallback."""
import pytest

# pylint: disable=import-outside-toplevel


@pytest.mark.github
def test_local_write_needs_cloud():
    from miot.common import local_write_needs_cloud

    assert local_write_needs_cloud(-9999) is True
    assert local_write_needs_cloud(-10006) is True
    assert local_write_needs_cloud(-4002) is True
    assert local_write_needs_cloud(0) is False
    assert local_write_needs_cloud(1) is False
    assert local_write_needs_cloud(-704042011) is False
    assert local_write_needs_cloud(None) is False


@pytest.mark.github
def test_should_start_cloud_write():
    from miot.common import (
        direct_write_timeout_ms, local_write_grace_sec,
        should_start_cloud_write)

    assert local_write_grace_sec() < 1
    assert direct_write_timeout_ms() <= 2000
    assert should_start_cloud_write(False, None) is True
    assert should_start_cloud_write(True, None) is True
    assert should_start_cloud_write(True, -9999) is True
    assert should_start_cloud_write(True, -10006) is True
    assert should_start_cloud_write(True, -4002) is True
    assert should_start_cloud_write(True, 0) is False
    assert should_start_cloud_write(True, 1) is False
    assert should_start_cloud_write(True, -704042011) is False


@pytest.mark.github
def test_prefers_cloud_write():
    from miot.common import prefers_cloud_write

    assert prefers_cloud_write('yeelink.light.lamp39') is True
    assert prefers_cloud_write('yeelink.light.lamp27') is True
    assert prefers_cloud_write('hotata.airer.d10zm') is False
    assert prefers_cloud_write('yeelink.bhf_light.v1') is False
    assert prefers_cloud_write(None) is False
    assert prefers_cloud_write('') is False


@pytest.mark.github
def test_ambient_on_retries_bool_as_int():
    from miot.common import prop_codes_win, reject_bool_as_int

    params = [{'siid': 4, 'piid': 1, 'value': True}]
    assert prop_codes_win([0, -704220043]) is True
    assert prop_codes_win([-704220043]) is False
    assert prop_codes_win([]) is False
    assert prop_codes_win(None) is False
    retried = reject_bool_as_int(params, [-704220043])
    assert retried == [{'siid': 4, 'piid': 1, 'value': 1}]
    assert reject_bool_as_int(params, [0]) is None
    assert reject_bool_as_int(
        [{'siid': 4, 'piid': 1, 'value': 1}], [-704220043]) is None


@pytest.mark.github
def test_cloud_value_rejected():
    from miot.common import cloud_value_rejected

    assert cloud_value_rejected(-704220043) is True
    assert cloud_value_rejected(-706012043) is True
    assert cloud_value_rejected(-4005) is True
    assert cloud_value_rejected(0) is False
    assert cloud_value_rejected(-9999) is False
    assert cloud_value_rejected(None) is False


@pytest.mark.github
def test_on_with_bright_level():
    from miot.common import on_with_bright_level

    assert on_with_bright_level(40, 10, 1, 100) == 40
    assert on_with_bright_level(None, 10, 1, 100) == 10
    assert on_with_bright_level(None, None, 1, 100) == 100
    assert on_with_bright_level(0, 10, 1, 100) == 1
    assert on_with_bright_level(180, 10, 1, 100) == 100
    assert on_with_bright_level(40.6, None, 1, 100) == 41
