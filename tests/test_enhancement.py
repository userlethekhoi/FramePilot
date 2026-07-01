import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio

from app.application.services.enhancement_service import EnhancementService
from app.application.services.job_queue import JobQueueManager
from app.core.entities.project import Project
from app.core.interfaces.enhancement import BaseEnhancer
from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProjectRepository,
)
from app.modules.enhancement.enhancement_hub import EnhancementHub


def test_enhancement_hub() -> None:
    """Verifies default engine registration in the EnhancementHub."""
    hub = EnhancementHub()
    assert "ffmpeg" in hub.list_enhancers()

    # Dynamic registration
    mock_enhancer = MagicMock(spec=BaseEnhancer)
    hub.register_enhancer("mock_filter", mock_enhancer)
    assert "mock_filter" in hub.list_enhancers()
    assert hub.get_enhancer("mock_filter") is mock_enhancer


@pytest.fixture
def mock_enhancer_engine() -> BaseEnhancer:
    """Provides a mocked enhancement filter engine."""
    engine = MagicMock(spec=BaseEnhancer)
    
    from collections.abc import Callable
    async def mock_enhance(
        input_path: str,
        output_path: str,
        task_type: str,
        options: dict[str, Any],
        progress_callback: Callable[[float], None] | None = None,
    ) -> str:
        if progress_callback:
            progress_callback(100.0)
        # Write dummy output file to verify completion
        with open(output_path, "w") as f:
            f.write("mock_enhanced")
        return output_path

    engine.enhance = AsyncMock(side_effect=mock_enhance)
    return engine


@pytest_asyncio.fixture
async def enhancement_service(
    mock_enhancer_engine: BaseEnhancer,
    db_engine: DatabaseEngine,
    settings_manager: SettingsManager,
) -> EnhancementService:
    """Provides an EnhancementService configured with test dependencies."""
    hub = EnhancementHub()
    hub.register_enhancer("mock_filter", mock_enhancer_engine)

    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)
    job_queue = JobQueueManager(max_threads=1)

    return EnhancementService(
        enhancement_hub=hub,
        asset_repo=asset_repo,
        job_repo=job_repo,
        job_queue=job_queue,
        settings=settings_manager,
    )


@pytest.mark.asyncio
async def test_enhancement_workflow(
    enhancement_service: EnhancementService, db_engine: DatabaseEngine, qtbot: Any
) -> None:
    """Verifies that media quality enhancement filters run, generate files, and save DB states."""
    proj_repo = SqlAlchemyProjectRepository(db_engine)
    asset_repo = SqlAlchemyAssetRepository(db_engine)

    # Save test project
    project = await proj_repo.save(Project(name="Enhance Project", path="/tmp"))
    project_id = project.id
    assert project_id is not None

    # Write a temporary dummy media file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
        temp_video.write(b"fake mp4 video content")
        temp_video_path = temp_video.name

    try:
        completed_events = []

        def on_completed(out_path: str) -> None:
            completed_events.append(out_path)

        # Submit upscale job
        job_id = enhancement_service.submit_enhancement_job(
            project_id=project_id,
            input_path=temp_video_path,
            task_type="upscale",
            options={"provider": "mock_filter", "scale_multiplier": 2},
            on_completed_ui=on_completed,
        )

        assert job_id is not None
        qtbot.waitUntil(lambda: len(completed_events) > 0, timeout=4000)

        # Verify output enhanced video created
        output_file = completed_events[0]
        assert os.path.exists(output_file)
        assert output_file.endswith("_upscale.mp4")

        # Verify DB assets registered
        assets = await asset_repo.list_by_project(project_id)
        assert len(assets) == 1
        assert assets[0].asset_type == "video"
        assert "upscale Enhanced" in assets[0].name

    finally:
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        
        enhanced_dir = os.path.join("storage", "enhanced")
        if os.path.exists(enhanced_dir):
            for file in os.listdir(enhanced_dir):
                os.remove(os.path.join(enhanced_dir, file))
            os.rmdir(enhanced_dir)
