import importlib
import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.exceptions import PluginError
from app.plugins.sdk.plugin_base import BasePlugin, PluginContext


class PluginManager:
    """Discovers, validates, dynamically imports, and manages custom external plugins."""

    def __init__(self, plugins_dir: str | Path, context: PluginContext) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.context = context
        self._plugins: dict[str, BasePlugin] = {}
        self._manifests: dict[str, dict[str, Any]] = {}

    def discover_and_load(self) -> None:
        """Scans the plugins directory and loads all valid detected plugins."""
        if not self.plugins_dir.exists():
            try:
                self.plugins_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error("Failed to create plugins directory {}: {}", self.plugins_dir, e)
                return

        logger.info("Scanning for plugins in: {}", self.plugins_dir.absolute())

        # Traverse directories in search of plugin.json manifests
        for item in self.plugins_dir.iterdir():
            if item.is_dir():
                manifest_path = item / "plugin.json"
                if manifest_path.exists():
                    try:
                        self._load_plugin_from_dir(item, manifest_path)
                    except PluginError as e:
                        logger.error("Failed to load plugin from {}: {}", item.name, e)
                    except Exception as e:
                        logger.exception(
                            "Unexpected error loading plugin from {}: {}", item.name, e
                        )

    def _load_plugin_from_dir(self, plugin_dir: Path, manifest_path: Path) -> None:
        """Loads a single plugin from its directory and configuration manifest."""
        # 1. Parse Manifest
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            raise PluginError(f"Failed to read or parse plugin.json: {e}") from e

        # Validate mandatory manifest properties
        required_fields = ["plugin_id", "name", "version", "entry_point"]
        for field in required_fields:
            if field not in manifest:
                raise PluginError(f"Plugin manifest is missing required field: '{field}'")

        plugin_id = manifest["plugin_id"]
        entry_point = manifest["entry_point"]

        if plugin_id in self._plugins:
            logger.warning("Plugin ID '{}' is already loaded. Skipping.", plugin_id)
            return

        # 2. Add plugin path to sys.path to enable dynamic importing
        sys.path.insert(0, str(plugin_dir.absolute()))

        # 3. Import module and locate plugin class
        # entry_point format: module_name:ClassName
        if ":" not in entry_point:
            raise PluginError(
                f"Invalid entry_point format '{entry_point}'. Expected 'module_name:ClassName'"
            )

        module_name, class_name = entry_point.split(":", 1)

        try:
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
        except Exception as e:
            raise PluginError(f"Failed to import plugin entry point '{entry_point}': {e}") from e

        # 4. Instantiate and validate inheritance
        if not issubclass(plugin_class, BasePlugin):
            raise PluginError(f"Plugin class '{class_name}' must inherit from BasePlugin.")

        try:
            plugin_instance = plugin_class()
            plugin_instance.initialize(self.context)

            # Store plugin reference
            self._plugins[plugin_id] = plugin_instance
            self._manifests[plugin_id] = manifest
            logger.info(
                "Successfully loaded plugin: {} v{} [{}]",
                manifest["name"],
                manifest["version"],
                plugin_id,
            )
        except Exception as e:
            raise PluginError(f"Failed during plugin initialization: {e}") from e

    def get_plugin(self, plugin_id: str) -> BasePlugin | None:
        """Returns the loaded instance of the specified plugin, or None."""
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> dict[str, dict[str, Any]]:
        """Returns metadata for all loaded plugins."""
        return dict(self._manifests)

    def shutdown_all(self) -> None:
        """Gracefully shuts down and unloads all plugins."""
        for plugin_id, plugin in list(self._plugins.items()):
            try:
                plugin.shutdown()
                logger.info("Successfully shut down plugin: {}", plugin_id)
            except Exception as e:
                logger.error("Error shutting down plugin {}: {}", plugin_id, e)
        self._plugins.clear()
        self._manifests.clear()
