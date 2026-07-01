from abc import ABC, abstractmethod
from typing import Any, List
from app.core.interfaces.speech import TranscriptionSegment


class BaseTextToSpeech(ABC):
    """Abstract interface governing all text-to-speech voice synthesis engines."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        options: dict[str, Any],
    ) -> str:
        """Synthesizes text to a single audio file and returns the path to the file."""
        pass

    @abstractmethod
    async def synthesize_segments(
        self,
        segments: List[TranscriptionSegment],
        voice_id: str,
        output_dir: str,
        options: dict[str, Any],
    ) -> List[str]:
        """Synthesizes list of timed segments to separate timed audio files."""
        pass
