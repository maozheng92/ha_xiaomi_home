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
    from miot.common import local_write_grace_sec, should_start_cloud_write

    assert local_write_grace_sec() < 1
    assert should_start_cloud_write(False, None) is True
    assert should_start_cloud_write(True, None) is True
    assert should_start_cloud_write(True, -9999) is True
    assert should_start_cloud_write(True, -10006) is True
    assert should_start_cloud_write(True, -4002) is True
    assert should_start_cloud_write(True, 0) is False
    assert should_start_cloud_write(True, 1) is False
    assert should_start_cloud_write(True, -704042011) is False
