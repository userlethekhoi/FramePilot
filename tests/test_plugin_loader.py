import json
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.database.connection import DatabaseEngine
from app.plugins.loader import PluginManager
from app.plugins.sdk.plugin_base import BasePlugin, PluginContext


class DummyLoadedPlugin(BasePlugin):
    """A dummy plugin to verify loading initialization."""

    def initialize(self, context: PluginContext) -> None:
        self.initialized = True
        self.context = context

    def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture
def temp_plugins_dir() -> Generator[Path]:
    """Provides a temporary plugins directory for test execution."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def test_plugin_manager_lifecycle(
    temp_plugins_dir: Path, settings_manager: SettingsManager, db_engine: DatabaseEngine
) -> None:
    """Verifies scanning, manifest parsing, dynamic importing, and clean unload steps."""
    context = PluginContext(settings=settings_manager, db_engine=db_engine, app_version="0.1.0")

    # 1. Create a dummy plugin directory and files
    plugin_id = "test.dummy.plugin"
    dummy_dir = temp_plugins_dir / "dummy_plugin"
    dummy_dir.mkdir()

    manifest = {
        "plugin_id": plugin_id,
        "name": "Dummy Plugin",
        "version": "1.0.0",
        "entry_point": "dummy_mod:DummyTestPlugin",
    }

    with open(dummy_dir / "plugin.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # Write the Python module code
    module_code = """
from app.plugins.sdk.plugin_base import BasePlugin, PluginContext

class DummyTestPlugin(BasePlugin):
    def initialize(self, context: PluginContext) -> None:
        self.context = context
        self.initialized = True
        
    def shutdown(self) -> None:
        self.shutdown_called = True
"""
    with open(dummy_dir / "dummy_mod.py", "w", encoding="utf-8") as f:
        f.write(module_code)

    # 2. Instantiate manager and load plugins
    manager = PluginManager(temp_plugins_dir, context)
    manager.discover_and_load()

    # 3. Assertions
    loaded_plugins = manager.list_plugins()
    assert plugin_id in loaded_plugins
    assert loaded_plugins[plugin_id]["name"] == "Dummy Plugin"

    plugin_instance = manager.get_plugin(plugin_id)
    assert plugin_instance is not None
    assert plugin_instance.initialized is True
    assert plugin_instance.context is context

    # 4. Shutdown
    manager.shutdown_all()
    assert len(manager.list_plugins()) == 0
    assert plugin_instance.shutdown_called is True


def test_plugin_manager_invalid_manifest(
    temp_plugins_dir: Path, settings_manager: SettingsManager, db_engine: DatabaseEngine
) -> None:
    """Verifies that invalid manifests are safely skipped with logged warnings, not breaking loading loop."""
    context = PluginContext(settings=settings_manager, db_engine=db_engine, app_version="0.1.0")

    # Create directory with invalid (empty) plugin.json manifest
    dummy_dir = temp_plugins_dir / "invalid_plugin"
    dummy_dir.mkdir()

    with open(dummy_dir / "plugin.json", "w", encoding="utf-8") as f:
        f.write("{invalid-json}")

    manager = PluginManager(temp_plugins_dir, context)
    # Should not raise exception, just skip it and log error
    manager.discover_and_load()
    assert len(manager.list_plugins()) == 0
