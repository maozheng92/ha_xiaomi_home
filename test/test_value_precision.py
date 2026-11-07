# -*- coding: utf-8 -*-
"""Unit tests for integer property alignment."""
import pytest

# pylint: disable=import-outside-toplevel, unused-argument


def _int_prop(value_range):
    from types import SimpleNamespace
    from miot.miot_spec import MIoTSpecProperty

    spec = {
        'iid': 3,
        'type': 'urn:miot-spec-v2:property:color-temperature:0000000F',
        'description': 'Color Temperature',
    }
    return MIoTSpecProperty(
        spec=spec,
        service=SimpleNamespace(iid=2),
        format_='uint32',
        access=['read', 'write'],
        value_range=value_range)


@pytest.mark.github
def test_color_temp_stays_inside_leishi_range():
    """leishi.light.eps125 rejects values outside 3000-5700 with code -4005."""
    prop = _int_prop([3000, 5700, 1])
    assert prop.value_precision(4500) == 4500
    assert prop.value_precision(3000) == 3000
    assert prop.value_precision(5700) == 5700
    # Slider values a fraction past either end round off the grid.
    assert prop.value_precision(5700.6) == 5700
    assert prop.value_precision(2999.4) == 3000
    assert prop.value_precision(2000) == 3000
    assert prop.value_precision(6535) == 5700


@pytest.mark.github
def test_color_temp_keeps_nonzero_origin_step():
    """A step that does not divide from zero must stay on the spec grid."""
    prop = _int_prop([2700, 6500, 38])
    assert prop.value_precision(2700) == 2700
    assert prop.value_precision(2738) == 2738
    assert prop.value_precision(2720) == 2738
    assert prop.value_precision(6500) == 6500
    assert prop.value_precision(6535) == 6500
    assert prop.value_precision(0) == 2700


@pytest.mark.github
def test_reversed_range_is_clamped():
    prop = _int_prop([6500, 2700, 100])
    assert prop.value_precision(4000) == 4000
    assert prop.value_precision(1000) == 2700
    assert prop.value_precision(9000) == 6500


@pytest.mark.github
def test_int_without_range_rounds():
    prop = _int_prop(None)
    assert prop.value_precision(12.6) == 13
    assert prop.value_precision(None) is None


@pytest.mark.github
def test_wy_mode_name_survives_translation():
    from miot.miot_spec import MIoTSpecValueList

    value_list = MIoTSpecValueList.from_spec([
        {'name': 'WY', 'value': 0, 'description': '色温模式'},
        {'name': 'Reading', 'value': 1, 'description': '阅读模式'},
        {'name': 'Eye Protection', 'value': 9, 'description': '护眼模式'},
    ])
    assert value_list.get_value_by_name('wy') == 0
    assert value_list.get_value_by_name('eye_protection') == 9
    assert value_list.get_value_by_name('day') is None
