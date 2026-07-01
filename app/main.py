import asyncio
import sys
import aiosqlite

from loguru import logger
from PySide6.QtWidgets import QApplication

from app.application.di.container import Container
from app.application.services.download_service import DownloadService
from app.application.services.job_queue import JobQueueManager
from app.core.interfaces.downloader import BaseDownloader
from app.core.interfaces.repository import (
    AssetRepository,
    JobRepository,
    PresetRepository,
    ProjectRepository,
)
from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.config.translation import TranslationManager
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyPresetRepository,
    SqlAlchemyProjectRepository,
)
from app.infrastructure.logging_config import setup_logging
from app.modules.download.yt_dlp_downloader import YtDlpDownloader
from app.ui.themes.engine import ThemeEngine
from app.ui.viewmodels.downloader_viewmodel import DownloaderViewModel
from app.modules.speech.provider_hub import SpeechProviderHub
from app.application.services.stt_service import SpeechToTextService
from app.modules.translation.translator_hub import TranslatorHub
from app.application.services.translation_service import TranslationService
from app.modules.tts.tts_hub import TextToSpeechHub
from app.application.services.tts_service import TextToSpeechService
from app.modules.enhancement.enhancement_hub import EnhancementHub
from app.application.services.enhancement_service import EnhancementService
from app.ui.viewmodels.enhancement_viewmodel import EnhancementViewModel
from app.ui.viewmodels.stt_viewmodel import SpeechToTextViewModel
from app.application.services.workflow_engine import WorkflowEngine
from app.ui.viewmodels.workflow_viewmodel import WorkflowViewModel
from app.ui.viewmodels.settings_viewmodel import SettingsViewModel
from app.application.services.project_service import ProjectService
from app.ui.viewmodels.projects_viewmodel import ProjectsViewModel
from app.ui.views.main_window import MainWindow


async def initialize_database(db_engine: DatabaseEngine) -> None:
    """Initializes the database connection and runs table creations."""
    logger.info("Initializing database schemas...")
    db_engine.initialize()
    await db_engine.create_tables(Base.metadata)
    logger.info("Database schemas initialized successfully.")


def main() -> None:
    """Application bootstrap entry point."""
    # 1. Initialize Dependency Injection Container
    container = Container()

    # 2. Load settings manager
    try:
        settings_manager = SettingsManager("config.yaml")
    except Exception:
        sys.exit(1)

    container.register_singleton(SettingsManager, settings_manager)

    # 3. Setup logging config
    log_level = settings_manager.get("logging.level", "INFO")
    log_file = settings_manager.get("logging.file", "logs/app.log")
    rotation = settings_manager.get("logging.rotation", "10 MB")
    retention = settings_manager.get("logging.retention", "1 month")
    compression = settings_manager.get("logging.compression", "zip")

    setup_logging(
        log_level=log_level,
        log_file=log_file,
        rotation=rotation,
        retention=retention,
        compression=compression,
    )
    # 3.5. Configure localization
    TranslationManager.set_language(settings_manager.get("app.language", "en"))
    logger.info("Starting MediaFlow AI bootstrap...")

    # 4. Configure Database engine and repositories
    db_engine = DatabaseEngine(settings_manager)
    container.register_singleton(DatabaseEngine, db_engine)

    project_repo = SqlAlchemyProjectRepository(db_engine)
    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)
    preset_repo = SqlAlchemyPresetRepository(db_engine)

    container.register_singleton(ProjectRepository, project_repo)
    container.register_singleton(AssetRepository, asset_repo)
    container.register_singleton(JobRepository, job_repo)
    container.register_singleton(PresetRepository, preset_repo)

    # Sync run schema migration before GUI initializes
    try:
        asyncio.run(initialize_database(db_engine))
    except Exception as e:
        logger.exception("Database migration failed at startup: {}", e)
        sys.exit(1)

    # Setup thread pool job queue manager
    max_threads = settings_manager.get("performance.max_worker_threads", 4)
    job_queue = JobQueueManager(max_threads)
    container.register_singleton(JobQueueManager, job_queue)

    project_service = ProjectService(project_repo)
    container.register_singleton(ProjectService, project_service)

    projects_viewmodel = ProjectsViewModel(project_service)
    container.register_singleton(ProjectsViewModel, projects_viewmodel)

    # Register Downloader components
    downloader = YtDlpDownloader()
    container.register_singleton(BaseDownloader, downloader)

    download_service = DownloadService(
        downloader, asset_repo, job_repo, job_queue, settings_manager
    )
    container.register_singleton(DownloadService, download_service)

    downloader_viewmodel = DownloaderViewModel(download_service, job_queue)
    container.register_singleton(DownloaderViewModel, downloader_viewmodel)

    # Register Speech Recognition, Translation, and TTS components
    stt_hub = SpeechProviderHub()
    container.register_singleton(SpeechProviderHub, stt_hub)

    stt_service = SpeechToTextService(
        stt_hub, asset_repo, job_repo, job_queue, settings_manager
    )
    container.register_singleton(SpeechToTextService, stt_service)

    translator_hub = TranslatorHub()
    container.register_singleton(TranslatorHub, translator_hub)

    translation_service = TranslationService(
        translator_hub, asset_repo, job_repo, job_queue, settings_manager
    )
    container.register_singleton(TranslationService, translation_service)

    tts_hub = TextToSpeechHub()
    container.register_singleton(TextToSpeechHub, tts_hub)

    tts_service = TextToSpeechService(
        tts_hub, translation_service, asset_repo, job_repo, job_queue, settings_manager
    )
    container.register_singleton(TextToSpeechService, tts_service)

    stt_viewmodel = SpeechToTextViewModel(stt_service, translation_service, tts_service)
    container.register_singleton(SpeechToTextViewModel, stt_viewmodel)

    # Register Enhancement components
    enhancement_hub = EnhancementHub()
    container.register_singleton(EnhancementHub, enhancement_hub)

    enhancement_service = EnhancementService(
        enhancement_hub, asset_repo, job_repo, job_queue, settings_manager
    )
    container.register_singleton(EnhancementService, enhancement_service)

    enhancement_viewmodel = EnhancementViewModel(enhancement_service)
    container.register_singleton(EnhancementViewModel, enhancement_viewmodel)

    # Register Workflow components
    workflow_engine = WorkflowEngine(
        download_service,
        stt_service,
        translation_service,
        tts_service,
        enhancement_service,
        asset_repo,
        job_repo,
        job_queue,
        settings_manager,
    )
    container.register_singleton(WorkflowEngine, workflow_engine)

    workflow_viewmodel = WorkflowViewModel(workflow_engine)
    container.register_singleton(WorkflowViewModel, workflow_viewmodel)

    # 5. Initialize UI Theme engine
    theme_mode = settings_manager.get("theme.mode", "dark")
    theme_engine = ThemeEngine(theme_mode)
    container.register_singleton(ThemeEngine, theme_engine)

    settings_viewmodel = SettingsViewModel(settings_manager, theme_engine)
    container.register_singleton(SettingsViewModel, settings_viewmodel)

    # 6. Start Qt application loop
    app = QApplication(sys.argv)
    app.setApplicationName(settings_manager.get("app.name", "MediaFlow AI"))
    app.setApplicationVersion(settings_manager.get("app.version", "0.1.0"))

    # Create & display main window passing DI container
    main_window = MainWindow(container)
    main_window.show()

    logger.info("Bootstrap complete. Launching GUI main event loop.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
