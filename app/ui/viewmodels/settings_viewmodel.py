from typing import Any
from PySide6.QtCore import QObject, Signal, Slot
from loguru import logger
from app.infrastructure.config.settings import SettingsManager
from app.ui.themes.engine import ThemeEngine


class SettingsViewModel(QObject):
    """ViewModel representing configuration parameters and global app settings."""

    # Signal triggered when theme gets dynamically toggled
    theme_changed = Signal(str)  # "light" or "dark"

    def __init__(self, settings: SettingsManager, theme_engine: ThemeEngine) -> None:
        super().__init__()
        self._settings = settings
        self._theme_engine = theme_engine

    @property
    def theme_mode(self) -> str:
        return str(self._settings.get("theme.mode", "dark"))

    @property
    def storage_dir(self) -> str:
        return str(self._settings.get("paths.storage_dir", "storage"))

    @property
    def openai_api_key(self) -> str:
        return str(self._settings.get("api.openai_key", ""))

    @property
    def deepseek_api_key(self) -> str:
        return str(self._settings.get("api.deepseek_key", ""))

    @property
    def gpu_acceleration(self) -> bool:
        return bool(self._settings.get("hardware.gpu_acceleration", False))

    @Slot(str, str, str, str, bool)
    def save_settings(
        self,
        theme: str,
        storage: str,
        openai_key: str,
        deepseek_key: str,
        gpu_accel: bool,
    ) -> None:
        """Saves updated settings in memory and writes back to config.yaml."""
        logger.info("Saving settings: theme={}, storage={}, gpu={}", theme, storage, gpu_accel)

        # Detect if theme has changed to trigger stylesheet reload
        old_theme = self.theme_mode
        
        self._settings.set("theme.mode", theme)
        self._settings.set("paths.storage_dir", storage)
        self._settings.set("api.openai_key", openai_key)
        self._settings.set("api.deepseek_key", deepseek_key)
        self._settings.set("hardware.gpu_acceleration", gpu_accel)

        self._settings.save()

        if old_theme != theme:
            self._theme_engine.current_mode = theme
            self.theme_changed.emit(theme)
