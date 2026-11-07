# -*- coding: utf-8 -*-
"""The main light absorbs the radar switch."""
import pytest

# pylint: disable=import-outside-toplevel


class _Spec:
    def __init__(self, name: str) -> None:
        self.name = name


class _Entity:
    def __init__(self, name: str) -> None:
        self.spec = _Spec(name)
        self.props = set()


class _Prop:
    def __init__(self, name: str) -> None:
        self.name = name
        self.platform = 'switch'


@pytest.mark.github
def test_absorb_radar_into_main_light():
    from miot.common import absorb_radar_into_main_light

    radar = _Prop('radar-en')
    other = _Prop('follow-main-light')
    ambient = _Entity('ambient-light')
    main = _Entity('light')
    entities = {'light': [ambient, main]}
    props = {'switch': [radar, other]}

    assert absorb_radar_into_main_light(entities, props) is True
    assert radar in main.props
    assert radar not in ambient.props
    assert radar.platform == 'light'
    assert props['switch'] == [other]
    assert absorb_radar_into_main_light(entities, props) is False


@pytest.mark.github
def test_absorb_radar_without_main_light():
    from miot.common import absorb_radar_into_main_light

    radar = _Prop('radar-en')
    ambient = _Entity('ambient-light')
    props = {'switch': [radar]}

    assert absorb_radar_into_main_light(
        {'light': [ambient]}, props) is False
    assert props['switch'] == [radar]
    assert radar.platform == 'switch'
