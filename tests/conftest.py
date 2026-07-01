import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio

from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.models import Base


@pytest.fixture
def temp_config_file() -> Generator[Path]:
    """Provides a temporary config.yaml file path for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yaml"
        # Write default parameters
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("""
app:
  name: "Test MediaFlow AI"
  version: "0.1.0"
database:
  url: "sqlite+aiosqlite:///:memory:"
  echo: false
logging:
  level: "DEBUG"
paths:
  plugins_dir: "test_plugins"
""")
        yield config_path


@pytest.fixture
def settings_manager(temp_config_file: Path) -> SettingsManager:
    """Provides a configured SettingsManager instance pointing to the temp config file."""
    return SettingsManager(temp_config_file)


@pytest_asyncio.fixture
async def db_engine(settings_manager: SettingsManager) -> AsyncGenerator[DatabaseEngine]:
    """Provides a DatabaseEngine configured to run against an in-memory SQLite database."""
    engine = DatabaseEngine(settings_manager)
    engine.initialize()
    # Create schemas
    await engine.create_tables(Base.metadata)
    yield engine
    # Cleanup connection
    await engine.close()
