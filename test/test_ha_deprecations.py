# -*- coding: utf-8 -*-
"""Regression checks for Home Assistant deprecation migrations."""
import ast
from os import path

import pytest

ROOT = path.abspath(path.join(path.dirname(__file__), '..'))
INTEGRATION = path.join(ROOT, 'custom_components', 'xiaomi_home')

_NATIVE_TEMPERATURE = {
    'current_temperature': 'native_current_temperature',
    'target_temperature': 'native_target_temperature',
    'temperature_unit': 'native_temperature_unit',
}


def _parse(relative_path: str) -> ast.AST:
    file_path = path.join(INTEGRATION, relative_path)
    with open(file_path, 'r', encoding='utf-8') as source:
        return ast.parse(source.read(), filename=file_path)


def _assigns_native_helper(tree: ast.AST) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [
            target.id for target in node.targets
            if isinstance(target, ast.Name)]
        if '_USE_NATIVE_TEMPERATURE' not in targets:
            continue
        func = node.value
        if not isinstance(func, ast.Call):
            return False
        if not isinstance(func.func, ast.Name):
            return False
        return func.func.id == 'entity_uses_native_temperature'
    return False


def _class_def(tree: ast.AST, name: str) -> ast.ClassDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f'{name} was not found')


def _is_property(node: ast.FunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == 'property':
            return True
    return False


def _property_names(body: list[ast.stmt]) -> list[str]:
    names = []
    for node in body:
        if isinstance(node, ast.FunctionDef) and _is_property(node):
            names.append(node.name)
    return names


def _conditional_properties(class_node: ast.ClassDef) -> dict[bool, list[str]]:
    """Return properties defined under ``_USE_NATIVE_TEMPERATURE``."""
    found: dict[bool, list[str]] = {True: [], False: []}
    for node in class_node.body:
        if not isinstance(node, ast.If):
            continue
        if not isinstance(node.test, ast.Name):
            continue
        if node.test.id != '_USE_NATIVE_TEMPERATURE':
            continue
        found[True].extend(_property_names(node.body))
        found[False].extend(_property_names(node.orelse))
    return found


def _attr_branches(class_node: ast.ClassDef) -> dict[str, set[bool]]:
    """Map unit attributes to the native-flag branch that assigns them."""
    branches: dict[str, set[bool]] = {}

    def walk(nodes: list[ast.stmt], native_branch: bool | None) -> None:
        for node in nodes:
            if isinstance(node, ast.If) and isinstance(node.test, ast.Name):
                if node.test.id == '_USE_NATIVE_TEMPERATURE':
                    walk(node.body, True)
                    walk(node.orelse, False)
                    continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(node.body, native_branch)
                continue
            if isinstance(
                    node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                walk(getattr(node, 'body', []), native_branch)
                walk(getattr(node, 'orelse', []), native_branch)
                walk(getattr(node, 'finalbody', []), native_branch)
                for handler in getattr(node, 'handlers', []):
                    walk(handler.body, native_branch)
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Attribute):
                    continue
                if target.attr not in {
                        '_attr_temperature_unit',
                        '_attr_native_temperature_unit'}:
                    continue
                if native_branch is None:
                    raise AssertionError(
                        f'{target.attr} is assigned outside the native check')
                branches.setdefault(target.attr, set()).add(native_branch)

    walk(class_node.body, None)
    return branches


def _deprecated_provider(
    cls: type, base: type, name: str, native_names: frozenset[str]
) -> str | None:
    """Return the Home Assistant 2026.11 deprecation message, if any.

    This follows ``migrate_deprecated_entity_members``: a subclass may
    provide the native member, and a subclass that still provides only the
    deprecated member is reported.
    """
    provider = next(
        klass for klass in cls.__mro__
        if name in vars(klass) or not native_names.isdisjoint(vars(klass)))
    if provider is base or not native_names.isdisjoint(vars(provider)):
        return None
    return (
        f'{cls.__module__}::{cls.__qualname__} provides the deprecated '
        f'{name}')


def _temperature_entity(use_native: bool) -> type:
    """Build the climate feature hierarchy with one temperature API."""

    class ClimateEntity:
        """Stand-in for the core climate entity base."""
        native_temperature_unit = None
        native_current_temperature = None
        native_target_temperature = None

    class ServiceEntity:
        """Stand-in for the integration service entity."""

    class FeatureTargetTemperature(ServiceEntity, ClimateEntity):
        """Target temperature feature."""

        def _target_temperature(self) -> int:
            return 21

        if use_native:

            @property
            def native_target_temperature(self) -> int:
                return self._target_temperature()

        else:

            @property
            def target_temperature(self) -> int:
                return self._target_temperature()

    class FeatureTemperature(ServiceEntity, ClimateEntity):
        """Measured temperature feature."""

        def _current_temperature(self) -> int:
            return 18

        if use_native:

            @property
            def native_current_temperature(self) -> int:
                return self._current_temperature()

        else:

            @property
            def current_temperature(self) -> int:
                return self._current_temperature()

    class Heater(FeatureTargetTemperature, FeatureTemperature):
        """Concrete entity that inherits both temperature features."""

    return Heater


@pytest.mark.github
def test_removed_devices_use_scoped_lookup():
    tree = _parse('__init__.py')
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            calls.append(func.attr)
        elif isinstance(func, ast.Name):
            calls.append(func.id)
    assert 'async_get_device' not in calls
    assert 'lookup_device_entry' in calls


@pytest.mark.github
def test_platform_sources_split_temperature_api():
    expectations = {
        ('climate.py', 'FeatureTargetTemperature'): (
            ['native_target_temperature'], ['target_temperature']),
        ('climate.py', 'FeatureTemperature'): (
            ['native_current_temperature'], ['current_temperature']),
        ('water_heater.py', 'WaterHeater'): (
            ['native_current_temperature', 'native_target_temperature'],
            ['current_temperature', 'target_temperature']),
    }
    for (relative_path, class_name), (native, legacy) in expectations.items():
        tree = _parse(relative_path)
        assert _assigns_native_helper(tree)
        class_node = _class_def(tree, class_name)
        properties = _conditional_properties(class_node)
        assert properties[True] == native
        assert properties[False] == legacy
        branches = _attr_branches(class_node)
        if class_name == 'FeatureTemperature':
            assert not branches
            continue
        assert branches == {
            '_attr_native_temperature_unit': {True},
            '_attr_temperature_unit': {False},
        }


@pytest.mark.github
def test_native_temperature_api_is_not_reported_deprecated():
    heater = _temperature_entity(True)
    base = next(
        cls for cls in heater.__mro__ if cls.__name__ == 'ClimateEntity')
    for deprecated, native in _NATIVE_TEMPERATURE.items():
        message = _deprecated_provider(
            heater, base, deprecated, frozenset({
                native, f'_attr_{native}'}))
        assert message is None
    assert heater().native_target_temperature == 21
    assert heater().native_current_temperature == 18
    assert 'target_temperature' not in vars(heater)
    assert 'current_temperature' not in vars(heater)


@pytest.mark.github
def test_legacy_temperature_api_remains_available():
    heater = _temperature_entity(False)
    assert heater().target_temperature == 21
    assert heater().current_temperature == 18
    assert 'native_target_temperature' not in vars(heater)
    assert 'native_current_temperature' not in vars(heater)


@pytest.mark.github
def test_deprecated_temperature_property_is_reported():
    class ClimateEntity:
        """Base that still owns the deprecated member."""
        native_target_temperature = None

    class FeatureTargetTemperature(ClimateEntity):
        """Feature that only provides the removed property name."""

        @property
        def target_temperature(self) -> int:
            return 21

    message = _deprecated_provider(
        FeatureTargetTemperature,
        ClimateEntity,
        'target_temperature',
        frozenset({
            'native_target_temperature',
            '_attr_native_target_temperature'}))
    assert message is not None
    assert 'provides the deprecated target_temperature' in message
