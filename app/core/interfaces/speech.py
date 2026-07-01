from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any, List, Optional


@dataclass
class TranscriptionSegment:
    """Represents a single segment of transcribed text with timestamps and speaker identifiers."""
    start: float  # seconds
    end: float  # seconds
    text: str
    speaker_id: Optional[str] = None


@dataclass
class TranscriptionResult:
    """Represents the complete output of a speech-to-text operation."""
    segments: List[TranscriptionSegment] = field(default_factory=list)
    language: str = "en"
    full_text: str = ""
    duration: float = 0.0


class BaseSpeechToTextProvider(ABC):
    """Abstract interface governing all local and cloud Speech-to-Text (STT) providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        options: dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> TranscriptionResult:
        """Transcribes an audio file on a background worker thread.
        
        Args:
            audio_path: Path to the local audio file (.wav, .mp3, etc.).
            options: Configuration options (e.g. language, model quality, API keys).
            progress_callback: Callback receiving progress percentage float (0.0 to 100.0).
            
        Returns:
            A TranscriptionResult containing segmented text and metadata.
        """
        pass
