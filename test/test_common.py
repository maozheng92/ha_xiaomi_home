# -*- coding: utf-8 -*-
"""Unit test for miot_common.py."""
import pytest

# pylint: disable=import-outside-toplevel, unused-argument


@pytest.mark.github
def test_entity_uses_native_temperature():
    from miot.common import entity_uses_native_temperature

    class Legacy:
        """Entity base from before the native temperature rename."""
        temperature_unit = '°C'

    class Native(Legacy):
        """Entity base that exposes native_temperature_unit."""
        native_temperature_unit = '°C'

    class Child(Native):
        """Integration entity that inherits the native temperature API."""

    assert not entity_uses_native_temperature(Legacy)
    assert entity_uses_native_temperature(Native)
    assert entity_uses_native_temperature(Child)


@pytest.mark.github
def test_lookup_device_entry_uses_config_entry_scope():
    from miot.common import lookup_device_entry

    class Registry:
        """Registry that supports config-entry scoped identifiers."""

        def __init__(self) -> None:
            self.calls = []

        def async_get_device_by_identifier(self, identifier, config_entry_id):
            self.calls.append(('scoped', identifier, config_entry_id))
            return 'scoped-device'

        def async_get_device(self, identifiers=None, connections=None):
            self.calls.append(('legacy', identifiers, connections))
            return 'legacy-device'

    registry = Registry()
    identifier = ('xiaomi_home', 'cn_abc')
    found = lookup_device_entry(registry, identifier, 'entry-1')
    assert found == 'scoped-device'
    assert registry.calls == [('scoped', identifier, 'entry-1')]


@pytest.mark.github
def test_lookup_device_entry_legacy_registry():
    from miot.common import lookup_device_entry

    class Registry:
        """Registry from before identifiers were scoped to a config entry."""

        def async_get_device(self, identifiers=None, connections=None):
            return identifiers, connections

    identifier = ('xiaomi_home', 'cn_abc')
    found = lookup_device_entry(Registry(), identifier, 'entry-1')
    assert found == ({identifier}, None)


@pytest.mark.github
def test_miot_matcher():
    from miot.common import MIoTMatcher

    matcher: MIoTMatcher = MIoTMatcher()
    # Add
    for l1 in range(1, 11):
        matcher[f'test/{l1}/#'] = f'test/{l1}/#'
        for l2 in range(1, 11):
            matcher[f'test/{l1}/{l2}'] = f'test/{l1}/{l2}'
            if not matcher.get(topic=f'test/+/{l2}'):
                matcher[f'test/+/{l2}'] = f'test/+/{l2}'
    # Match
    match_result: list[str] = list(matcher.iter_all_nodes())
    assert len(match_result) == 120
    match_result: list[str] = list(matcher.iter_match(topic='test/1/1'))
    assert len(match_result) == 3
    assert set(match_result) == set(['test/1/1', 'test/+/1', 'test/1/#'])
    # Delete
    if matcher.get(topic='test/1/1'):
        del matcher['test/1/1']
    assert len(list(matcher.iter_all_nodes())) == 119
    match_result: list[str] = list(matcher.iter_match(topic='test/1/1'))
    assert len(match_result) == 2
    assert set(match_result) == set(['test/+/1', 'test/1/#'])
