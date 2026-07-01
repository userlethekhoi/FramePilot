import os
import time
from collections.abc import Callable
from typing import Any, Optional
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import (
    BaseSpeechToTextProvider,
    TranscriptionResult,
    TranscriptionSegment,
)


class LocalWhisperSpeechToTextProvider(BaseSpeechToTextProvider):
    """Local offline Speech-to-Text provider wrapping the openai-whisper package."""

    async def transcribe(
        self,
        audio_path: str,
        options: dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> TranscriptionResult:
        
        if not os.path.exists(audio_path):
            raise ServiceError(f"Audio file not found at: {audio_path}")

        model_name = options.get("model_size", "base")
        logger.info("Initializing Local Whisper model: {} for file: {}", model_name, audio_path)

        if progress_callback:
            progress_callback(10.0)

        # Support mock mode for unit testing and quick demonstrations without torch dependency
        if options.get("mock", False) or os.getenv("MEDIAFLOW_STT_MOCK") == "1":
            return await self._run_mock_transcribe(audio_path, progress_callback)

        import asyncio
        return await asyncio.to_thread(self._transcribe_sync, audio_path, model_name, options, progress_callback)

    def _transcribe_sync(
        self,
        audio_path: str,
        model_name: str,
        options: dict[str, Any],
        progress_callback: Optional[Callable[[float], None]],
    ) -> TranscriptionResult:
        try:
            import whisper
        except ImportError as e:
            raise ServiceError(
                "Local Whisper dependencies not found. "
                "Please run: pip install openai-whisper torch"
            ) from e

        try:
            if progress_callback:
                progress_callback(25.0)

            # Load model (downloads if not cached)
            logger.info("Loading local Whisper model '{}'...", model_name)
            model = whisper.load_model(model_name)

            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            if ffmpeg_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{os.environ.get('PATH', '')}"

            if progress_callback:
                progress_callback(50.0)

            logger.info("Transcribing audio file with Whisper model using ffmpeg at {}...", ffmpeg_dir)
            # Transcribe
            result = model.transcribe(audio_path, language=options.get("language"))

            if progress_callback:
                progress_callback(90.0)

            # Parse results
            segments = []
            for seg in result.get("segments", []):
                segments.append(
                    TranscriptionSegment(
                        start=float(seg.get("start", 0.0)),
                        end=float(seg.get("end", 0.0)),
                        text=seg.get("text", "").strip(),
                    )
                )

            full_text = result.get("text", "")
            detected_lang = result.get("language", "en")

            if progress_callback:
                progress_callback(100.0)

            return TranscriptionResult(
                segments=segments,
                language=detected_lang,
                full_text=full_text,
                duration=float(len(segments) * 2.5),  # Estimated duration if not present
            )

        except Exception as e:
            logger.exception("Local Whisper transcription failed: {}", e)
            raise ServiceError(f"Local Whisper transcription failed: {e}") from e

    async def _run_mock_transcribe(
        self, audio_path: str, progress_callback: Optional[Callable[[float], None]]
    ) -> TranscriptionResult:
        """Simulates a transcription job for quick testing."""
        logger.info("Running Mock Transcription for file: {}", audio_path)
        
        steps = [20.0, 50.0, 80.0, 100.0]
        for step in steps:
            time.sleep(0.1)
            if progress_callback:
                progress_callback(step)

        # Return a standard placeholder transcription matching general video audio
        segments = [
            TranscriptionSegment(
                start=0.0,
                end=3.5,
                text="Welcome to MediaFlow AI, the next-generation media processing studio.",
            ),
            TranscriptionSegment(
                start=4.0,
                end=8.2,
                text="In this video, we will showcase the local Whisper speech-to-text integration.",
            ),
        ]
        return TranscriptionResult(
            segments=segments,
            language="en",
            full_text=" ".join(s.text for s in segments),
            duration=8.2,
        )
