from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.database.connection import DatabaseEngine


@dataclass
class PluginContext:
    """Provides system utilities and database engine access to loaded plugins."""

    settings: SettingsManager
    db_engine: DatabaseEngine
    app_version: str


class BasePlugin(ABC):
    """Abstract Base Class all external and internal MediaFlow AI plugins must implement."""

    @abstractmethod
    def initialize(self, context: PluginContext) -> None:
        """Invoked immediately after the plugin is loaded by the PluginManager.

        Args:
            context: The shared application execution context containing managers.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Invoked when the application shuts down or the plugin is unloaded.

        Use this to release thread pools, sockets, database transactions, or file buffers.
        """
        pass
