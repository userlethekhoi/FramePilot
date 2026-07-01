import os
import tempfile
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio

from app.application.services.translation_service import TranslationService
from app.application.services.tts_service import TextToSpeechService
from app.application.services.job_queue import JobQueueManager
from app.core.entities.project import Project
from app.core.interfaces.speech import TranscriptionSegment
from app.core.interfaces.translation import BaseTranslator
from app.core.interfaces.tts import BaseTextToSpeech
from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProjectRepository,
)
from app.modules.translation.translator_hub import TranslatorHub
from app.modules.tts.tts_hub import TextToSpeechHub


@pytest.fixture
def mock_translator() -> BaseTranslator:
    """Provides a mocked translation engine."""
    translator = MagicMock(spec=BaseTranslator)
    
    # Configure mock translate methods
    translator.translate_text = AsyncMock(return_value="Bonjour le monde")
    
    async def mock_translate_segments(
        segments: list[TranscriptionSegment], target_lang: str, source_lang: Optional[str] = None
    ) -> list[TranscriptionSegment]:
        return [
            TranscriptionSegment(start=s.start, end=s.end, text=f"Tr: {s.text}")
            for s in segments
        ]
    translator.translate_segments = AsyncMock(side_effect=mock_translate_segments)
    
    return translator


@pytest.fixture
def mock_tts() -> BaseTextToSpeech:
    """Provides a mocked Text-to-Speech engine."""
    tts = MagicMock(spec=BaseTextToSpeech)
    
    tts.synthesize = AsyncMock(return_value="/tmp/audio.mp3")
    
    async def mock_synthesize_segments(
        segments: list[TranscriptionSegment], voice_id: str, output_dir: str, options: dict[str, Any]
    ) -> list[str]:
        return [
            os.path.join(output_dir, f"segment_{i:04d}.mp3")
            for i in range(len(segments))
        ]
    tts.synthesize_segments = AsyncMock(side_effect=mock_synthesize_segments)
    
    return tts


@pytest_asyncio.fixture
async def translation_service(
    mock_translator: BaseTranslator,
    db_engine: DatabaseEngine,
    settings_manager: SettingsManager,
) -> TranslationService:
    """Provides a TranslationService configured with test dependencies."""
    hub = TranslatorHub()
    hub.register_translator("mock_trans", mock_translator)

    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)
    job_queue = JobQueueManager(max_threads=1)

    return TranslationService(
        translator_hub=hub,
        asset_repo=asset_repo,
        job_repo=job_repo,
        job_queue=job_queue,
        settings=settings_manager,
    )


@pytest_asyncio.fixture
async def tts_service(
    mock_tts: BaseTextToSpeech,
    translation_service: TranslationService,
    db_engine: DatabaseEngine,
    settings_manager: SettingsManager,
) -> TextToSpeechService:
    """Provides a TextToSpeechService configured with test dependencies."""
    hub = TextToSpeechHub()
    hub.register_engine("mock_tts", mock_tts)

    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)
    job_queue = JobQueueManager(max_threads=1)

    return TextToSpeechService(
        tts_hub=hub,
        translation_service=translation_service,
        asset_repo=asset_repo,
        job_repo=job_repo,
        job_queue=job_queue,
        settings=settings_manager,
    )


@pytest.mark.asyncio
async def test_subtitle_translation_workflow(
    translation_service: TranslationService, db_engine: DatabaseEngine, qtbot: Any
) -> None:
    """Verifies that translation parsing, execution and database registration behaves correctly."""
    proj_repo = SqlAlchemyProjectRepository(db_engine)
    asset_repo = SqlAlchemyAssetRepository(db_engine)

    # Save test project
    project = await proj_repo.save(Project(name="Trans Project", path="/tmp"))
    project_id = project.id
    assert project_id is not None

    # Write a test SRT file
    srt_content = (
        "1\n"
        "00:00:01,000 --> 00:00:03,500\n"
        "Welcome to the show.\n"
        "\n"
        "2\n"
        "00:00:04,200 --> 00:00:08,000\n"
        "Let's see some magic.\n"
    )
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w", encoding="utf-8") as temp_sub:
        temp_sub.write(srt_content)
        temp_sub_path = temp_sub.name

    try:
        completed_events = []

        def on_completed(out_path: str) -> None:
            completed_events.append(out_path)

        # Submit translation job
        job_id = translation_service.submit_translation_job(
            project_id=project_id,
            subtitle_path=temp_sub_path,
            target_lang="fr",
            options={"provider": "mock_trans"},
            on_completed_ui=on_completed,
        )

        assert job_id is not None
        qtbot.waitUntil(lambda: len(completed_events) > 0, timeout=4000)

        # Verify translation output was created
        output_file = completed_events[0]
        assert os.path.exists(output_file)
        assert output_file.endswith("_fr.srt")

        with open(output_file, "r", encoding="utf-8") as f:
            output_content = f.read()

        # Check content contains translated side-effect tags
        assert "Tr: Welcome to the show." in output_content
        assert "Tr: Let's see some magic." in output_content

        # Verify DB assets registered
        assets = await asset_repo.list_by_project(project_id)
        assert len(assets) == 1
        assert assets[0].asset_type == "subtitle"
        assert assets[0].name.endswith("(fr Subtitles)")

    finally:
        if os.path.exists(temp_sub_path):
            os.remove(temp_sub_path)
        sub_dir = os.path.join("storage", "subtitles")
        if os.path.exists(sub_dir):
            for file in os.listdir(sub_dir):
                os.remove(os.path.join(sub_dir, file))
            os.rmdir(sub_dir)


@pytest.mark.asyncio
async def test_voice_synthesis_workflow(
    tts_service: TextToSpeechService, db_engine: DatabaseEngine, qtbot: Any
) -> None:
    """Verifies that text-to-speech job submits, synthesizes segments, and merges them correctly."""
    proj_repo = SqlAlchemyProjectRepository(db_engine)
    asset_repo = SqlAlchemyAssetRepository(db_engine)

    # Save test project
    project = await proj_repo.save(Project(name="TTS Project", path="/tmp"))
    project_id = project.id
    assert project_id is not None

    # Write a test SRT file
    srt_content = (
        "1\n"
        "00:00:01,000 --> 00:00:03,500\n"
        "Welcome to the show.\n"
    )
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w", encoding="utf-8") as temp_sub:
        temp_sub.write(srt_content)
        temp_sub_path = temp_sub.name

    try:
        completed_events = []

        def on_completed(out_path: str) -> None:
            completed_events.append(out_path)

        # Submit synthesis job
        job_id = tts_service.submit_synthesis_job(
            project_id=project_id,
            subtitle_path=temp_sub_path,
            voice_id="alloy",
            options={"provider": "mock_tts", "mock": True},
            on_completed_ui=on_completed,
        )

        assert job_id is not None
        qtbot.waitUntil(lambda: len(completed_events) > 0, timeout=4000)

        # Verify output audio file was created
        output_audio = completed_events[0]
        assert os.path.exists(output_audio)
        assert output_audio.endswith("_dubbed.mp3")

        # Verify DB assets registered
        assets = await asset_repo.list_by_project(project_id)
        assert len(assets) == 1
        assert assets[0].asset_type == "audio"
        assert "Dubbed Voice Track" in assets[0].name

    finally:
        if os.path.exists(temp_sub_path):
            os.remove(temp_sub_path)
        
        # Clean up output storage directories
        audio_dir = os.path.join("storage", "audio")
        if os.path.exists(audio_dir):
            for root, dirs, files in os.walk(audio_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(audio_dir)
