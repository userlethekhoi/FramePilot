import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio

from app.application.services.stt_service import SpeechToTextService
from app.application.services.job_queue import JobQueueManager
from app.core.entities.project import Project
from app.core.interfaces.speech import BaseSpeechToTextProvider, TranscriptionResult, TranscriptionSegment
from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProjectRepository,
)
from app.modules.speech.provider_hub import SpeechProviderHub


def test_speech_provider_hub() -> None:
    """Verifies that the SpeechProviderHub registers defaults and permits dynamic registration."""
    hub = SpeechProviderHub()
    
    # 1. Assert default registrations
    providers = hub.list_providers()
    assert "whisper" in providers
    assert "openai" in providers

    # 2. Assert dynamic mock registration
    mock_provider = MagicMock(spec=BaseSpeechToTextProvider)
    hub.register_provider("mock_stt", mock_provider)
    assert "mock_stt" in hub.list_providers()
    assert hub.get_provider("mock_stt") is mock_provider


@pytest_asyncio.fixture
async def mock_stt_provider() -> BaseSpeechToTextProvider:
    """Provides a mocked STT provider."""
    provider = MagicMock(spec=BaseSpeechToTextProvider)
    
    # Configure mock transcribe method
    segments = [
        TranscriptionSegment(start=0.0, end=2.5, text="Hello world"),
        TranscriptionSegment(start=2.5, end=5.0, text="This is MediaFlow AI"),
    ]
    provider.transcribe = AsyncMock(
        return_value=TranscriptionResult(
            segments=segments,
            language="en",
            full_text="Hello world This is MediaFlow AI",
            duration=5.0,
        )
    )
    return provider


@pytest_asyncio.fixture
async def stt_service(
    mock_stt_provider: BaseSpeechToTextProvider,
    db_engine: DatabaseEngine,
    settings_manager: SettingsManager,
) -> SpeechToTextService:
    """Provides an STT service configured with mock provider and test database."""
    hub = SpeechProviderHub()
    hub.register_provider("mock_stt", mock_stt_provider)

    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)
    job_queue = JobQueueManager(max_threads=1)

    return SpeechToTextService(
        provider_hub=hub,
        asset_repo=asset_repo,
        job_repo=job_repo,
        job_queue=job_queue,
        settings=settings_manager,
    )


@pytest.mark.asyncio
async def test_transcribe_job_submission(
    stt_service: SpeechToTextService, db_engine: DatabaseEngine, qtbot: Any
) -> None:
    """Verifies job queues submission, transcription execution, and subtitle assets storage."""
    proj_repo = SqlAlchemyProjectRepository(db_engine)
    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)

    # Save test project
    project = await proj_repo.save(Project(name="Test Project", path="/tmp"))
    project_id = project.id
    assert project_id is not None

    # Write a temporary fake audio file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
        temp_audio.write(b"RIFF....WAVEfmt ....data....")
        temp_audio_path = temp_audio.name

    try:
        completed_events = []

        def on_completed(res: TranscriptionResult) -> None:
            completed_events.append(res)

        # Submit transcription job
        job_id = stt_service.submit_transcribe_job(
            project_id=project_id,
            media_path=temp_audio_path,
            options={"provider": "mock_stt", "mock": True},
            on_completed_ui=on_completed,
        )

        assert job_id is not None

        # Wait for the background worker to execute the task
        qtbot.waitUntil(lambda: len(completed_events) > 0, timeout=4000)

        # Assert results
        assert len(completed_events) == 1
        res = completed_events[0]
        assert res.language == "en"
        assert len(res.segments) == 2
        assert res.segments[0].text == "Hello world"

        # Verify Job records updated in DB
        db_job = await job_repo.get_by_id(job_id)
        assert db_job is not None
        assert db_job.status == "COMPLETED"
        assert len(db_job.steps) == 1
        assert db_job.steps[0].status == "COMPLETED"
        assert db_job.steps[0].progress == 100.0

        # Verify Subtitle files exported
        base_name = os.path.splitext(os.path.basename(temp_audio_path))[0]
        expected_srt = os.path.join("storage", "subtitles", f"{base_name}.srt")
        assert os.path.exists(expected_srt)

        # Verify Subtitle assets registered to Project in DB
        assets = await asset_repo.list_by_project(project_id)
        assert len(assets) == 1
        assert assets[0].asset_type == "subtitle"
        assert os.path.abspath(assets[0].file_path) == os.path.abspath(expected_srt)

    finally:
        # Clean up temporary files
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        # Clean up generated subtitles
        sub_dir = os.path.join("storage", "subtitles")
        if os.path.exists(sub_dir):
            for file in os.listdir(sub_dir):
                os.remove(os.path.join(sub_dir, file))
            os.rmdir(sub_dir)


def test_subtitle_formatting_utilities() -> None:
    """Verifies that SRT and VTT subtitle formatting helpers behave as specified."""
    service = SpeechToTextService(
        provider_hub=MagicMock(),
        asset_repo=MagicMock(),
        job_repo=MagicMock(),
        job_queue=MagicMock(),
        settings=MagicMock(),
    )

    segments = [
        TranscriptionSegment(start=1.25, end=3.5, text="Hello"),
        TranscriptionSegment(start=3.6, end=10.055, text="Welcome to MediaFlow"),
    ]

    # SRT Format check
    srt = service.generate_srt(segments)
    expected_srt_lines = [
        "1",
        "00:00:01,250 --> 00:00:03,500",
        "Hello",
        "",
        "2",
        "00:00:03,600 --> 00:00:10,055",
        "Welcome to MediaFlow",
    ]
    assert srt.strip() == "\n".join(expected_srt_lines).strip()

    # VTT Format check
    vtt = service.generate_vtt(segments)
    expected_vtt_lines = [
        "WEBVTT",
        "",
        "00:00:01.250 --> 00:00:03.500",
        "Hello",
        "",
        "00:00:03.600 --> 00:00:10.055",
        "Welcome to MediaFlow",
    ]
    assert vtt.strip() == "\n".join(expected_vtt_lines).strip()
