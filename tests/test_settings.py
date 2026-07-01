from pathlib import Path

import pytest

from app.core.exceptions import ConfigError
from app.infrastructure.config.settings import SettingsManager


def test_settings_load_success(settings_manager: SettingsManager) -> None:
    """Verifies that settings load initial parameters successfully."""
    assert settings_manager.get("app.name") == "Test MediaFlow AI"
    assert settings_manager.get("database.url") == "sqlite+aiosqlite:///:memory:"


def test_settings_get_default(settings_manager: SettingsManager) -> None:
    """Verifies retrieval of default fallback values for non-existent settings keys."""
    assert settings_manager.get("nonexistent.key", "default_val") == "default_val"
    assert settings_manager.get("app.nonexistent") is None


def test_settings_set_and_save(settings_manager: SettingsManager, temp_config_file: Path) -> None:
    """Verifies updates are saved to memory and successfully written to YAML disk files."""
    settings_manager.set("app.name", "Updated Test Name")
    settings_manager.set("new_section.key", 123)

    assert settings_manager.get("app.name") == "Updated Test Name"
    assert settings_manager.get("new_section.key") == 123

    # Save back to file
    settings_manager.save()

    # Create another manager and load same file to confirm writing
    new_manager = SettingsManager(temp_config_file)
    assert new_manager.get("app.name") == "Updated Test Name"
    assert new_manager.get("new_section.key") == 123


def test_settings_load_invalid_file() -> None:
    """Verifies that loading a non-existent configuration path raises ConfigError."""
    with pytest.raises(ConfigError):
        SettingsManager("non_existent_file.yaml")
