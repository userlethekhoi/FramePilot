from abc import ABC, abstractmethod
from typing import Any, List, Optional
from app.core.interfaces.speech import TranscriptionSegment


class BaseTranslator(ABC):
    """Abstract interface governing all translation providers (Google, DeepL, GPT)."""

    @abstractmethod
    async def translate_text(
        self,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> str:
        """Translates a single block of text."""
        pass

    @abstractmethod
    async def translate_segments(
        self,
        segments: List[TranscriptionSegment],
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> List[TranscriptionSegment]:
        """Translates a list of timed transcription segments while keeping timestamps intact."""
        pass
