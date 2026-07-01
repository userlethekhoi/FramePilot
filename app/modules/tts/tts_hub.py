from typing import Dict, List
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.tts import BaseTextToSpeech
from app.modules.tts.openai_tts import OpenAiTextToSpeech
from app.modules.tts.local_tts import LocalTextToSpeech


class TextToSpeechHub:
    """Manages active text-to-speech voice synthesis engines."""

    def __init__(self) -> None:
        self._engines: Dict[str, BaseTextToSpeech] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_engine("local", LocalTextToSpeech())
        self.register_engine("openai", OpenAiTextToSpeech())
        logger.info("TextToSpeechHub initialized with default engines: local, openai")

    def register_engine(self, name: str, engine: BaseTextToSpeech) -> None:
        """Permits registering dynamic custom or plugin TTS engines."""
        self._engines[name.lower()] = engine
        logger.debug("Registered voice synthesis engine: {}", name)

    def get_engine(self, name: str) -> BaseTextToSpeech:
        """Retrieves registered TTS engine class by name."""
        engine = self._engines.get(name.lower())
        if not engine:
            raise ServiceError(
                f"TTS voice engine '{name}' is not registered. "
                f"Registered engines: {', '.join(self.list_engines())}"
            )
        return engine

    def list_engines(self) -> List[str]:
        """Lists registered voice engine names."""
        return list(self._engines.keys())
