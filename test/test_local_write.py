# -*- coding: utf-8 -*-
"""Unit test for local write cloud fallback."""
import pytest

# pylint: disable=import-outside-toplevel


@pytest.mark.github
def test_local_write_needs_cloud():
    from miot.common import local_write_needs_cloud

    assert local_write_needs_cloud(-9999) is True
    assert local_write_needs_cloud(-10006) is True
    assert local_write_needs_cloud(0) is False
    assert local_write_needs_cloud(1) is False
    assert local_write_needs_cloud(-704042011) is False
    assert local_write_needs_cloud(None) is False
