from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from app.core.exceptions import ConfigError


class SettingsManager:
    """Thread-safe manager for loading, querying, and updating YAML configurations."""

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self._settings: dict[str, Any] = {}
        self._lock = Lock()
        self.load()

    def load(self) -> None:
        """Loads configuration from the YAML file on disk."""
        with self._lock:
            if not self.config_path.exists():
                raise ConfigError(f"Configuration file not found at: {self.config_path.absolute()}")

            try:
                with open(self.config_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not isinstance(data, dict):
                        raise ConfigError(
                            "Configuration file must contain a key-value mapping structure."
                        )
                    self._settings = data
            except yaml.YAMLError as e:
                raise ConfigError(f"Failed to parse YAML configuration file: {e}") from e
            except Exception as e:
                raise ConfigError(f"Unexpected error loading configuration: {e}") from e

    def get(self, key_path: str, default: Any = None) -> Any:
        """Retrieves a configuration value using dot notation (e.g. 'app.name')."""
        with self._lock:
            parts = key_path.split(".")
            current: Any = self._settings
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current

    def set(self, key_path: str, value: Any) -> None:
        """Updates a configuration value in memory using dot notation (e.g. 'theme.mode')."""
        with self._lock:
            parts = key_path.split(".")
            current: Any = self._settings
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value

    def save(self) -> None:
        """Saves current memory settings back to the configuration file on disk."""
        with self._lock:
            # Ensure parent directories exist
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(self._settings, f, default_flow_style=False, sort_keys=False)
            except Exception as e:
                raise ConfigError(f"Failed to save configuration to {self.config_path}: {e}") from e

    @property
    def raw_settings(self) -> dict[str, Any]:
        """Returns a copy of the loaded raw settings dictionary."""
        with self._lock:
            return dict(self._settings)
