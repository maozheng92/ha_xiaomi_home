# -*- coding: utf-8 -*-
"""Unit test for curtain restart helpers."""
import pytest

# pylint: disable=import-outside-toplevel


@pytest.mark.github
def test_cover_position_reached():
    from miot.common import cover_position_reached

    assert cover_position_reached(None, 0) is False
    assert cover_position_reached(0, 0) is True
    assert cover_position_reached(100, 100) is True
    assert cover_position_reached(0, 100) is False
    assert cover_position_reached(2, 0, dead_zone=5) is True
    assert cover_position_reached(6, 0, dead_zone=5) is False


@pytest.mark.github
def test_should_not_refresh_target_when_current_exists():
    from miot.common import should_refresh_cover_prop

    names = {'status', 'current-position', 'target-position'}
    assert should_refresh_cover_prop('current-position', names) is True
    assert should_refresh_cover_prop('status', names) is True
    assert should_refresh_cover_prop('target-position', names) is False
    assert should_refresh_cover_prop(
        'target-position', {'target-position'}) is True
