from typing import Any
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.application.services.download_service import DownloadService
from app.application.services.job_queue import JobQueueManager
from app.core.entities.project import Project
from app.core.interfaces.downloader import BaseDownloader, DownloadResult
from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProjectRepository,
)
from app.modules.download.yt_dlp_downloader import YtDlpDownloader


@pytest_asyncio.fixture
async def mock_downloader() -> BaseDownloader:
    """Provides a mocked BaseDownloader instance."""
    downloader = MagicMock(spec=BaseDownloader)

    # Setup mock return values using AsyncMock
    downloader.extract_metadata = AsyncMock(
        return_value={
            "title": "Mock Video Title",
            "thumbnail": "http://example.com/thumb.jpg",
            "duration": 300.0,
            "uploader": "Uploader Name",
            "formats": [
                {"format_id": "18", "ext": "mp4", "resolution": "640x360", "filesize": 10240}
            ],
        }
    )

    downloader.download = AsyncMock(
        return_value=DownloadResult(
            success=True,
            file_path="/mock/path/video.mp4",
            title="Mock Video Title",
            thumbnail_url="http://example.com/thumb.jpg",
            duration=300.0,
            width=640,
            height=360,
            file_size=10240,
        )
    )
    return downloader


@pytest_asyncio.fixture
async def download_service(
    mock_downloader: BaseDownloader,
    db_engine: DatabaseEngine,
    settings_manager: SettingsManager,
) -> DownloadService:
    """Provides a DownloadService configured with mock downloader and test repositories."""
    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)
    job_queue = JobQueueManager(max_threads=1)

    return DownloadService(
        downloader=mock_downloader,
        asset_repo=asset_repo,
        job_repo=job_repo,
        job_queue=job_queue,
        settings=settings_manager,
    )


@pytest.mark.asyncio
async def test_download_service_metadata(download_service: DownloadService) -> None:
    """Verifies that download service parses metadata properties correctly."""
    info = await download_service.get_media_info("https://youtube.com/watch?v=123")

    assert info["title"] == "Mock Video Title"
    assert info["duration"] == 300.0
    assert info["uploader"] == "Uploader Name"
    assert len(info["formats"]) == 1
    assert info["formats"][0]["resolution"] == "640x360"


@pytest.mark.asyncio
async def test_download_service_job_submission(
    download_service: DownloadService, db_engine: DatabaseEngine, qtbot: Any
) -> None:
    """Verifies job logging, execution dispatch, and asset registration upon completion."""
    proj_repo = SqlAlchemyProjectRepository(db_engine)
    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)

    # Save test project
    project = await proj_repo.save(Project(name="Test Project", path="/tmp"))
    project_id = project.id
    assert project_id is not None

    completed_events = []

    def on_completed(res: DownloadResult) -> None:
        completed_events.append(res)

    # Submit download job
    job_id = download_service.submit_download_job(
        project_id=project_id,
        url="https://youtube.com/watch?v=123",
        options={"quality": "highest"},
        on_completed_ui=on_completed,
    )

    assert job_id is not None

    # Wait for background job execution to finish
    qtbot.waitUntil(lambda: len(completed_events) > 0, timeout=4000)

    # 1. Verify Job state updated to COMPLETED in DB
    job_record = await job_repo.get_by_id(job_id)
    assert job_record is not None
    assert job_record.status == "COMPLETED"
    assert len(job_record.steps) == 1
    assert job_record.steps[0].status == "COMPLETED"
    assert job_record.steps[0].progress == 100.0

    # 2. Verify Asset registered to project in DB
    assets = await asset_repo.list_by_project(project_id)
    assert len(assets) == 1
    assert assets[0].name == "Mock Video Title"
    assert assets[0].file_path == "/mock/path/video.mp4"
    assert assets[0].asset_type == "video"


@patch("yt_dlp.YoutubeDL")
@pytest.mark.asyncio
async def test_yt_dlp_downloader_metadata(mock_ytdl: MagicMock) -> None:
    """Verifies that YtDlpDownloader correctly invokes the yt-dlp API."""
    instance = mock_ytdl.return_value.__enter__.return_value
    instance.extract_info.return_value = {
        "title": "YtDlp Title",
        "thumbnail": "thumb.png",
        "duration": 120,
    }

    downloader = YtDlpDownloader()
    info = await downloader.extract_metadata("https://youtube.com/watch?v=abc")

    assert info["title"] == "YtDlp Title"
    instance.extract_info.assert_called_once_with("https://youtube.com/watch?v=abc", download=False)
