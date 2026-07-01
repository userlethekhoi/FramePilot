from typing import Dict, List, Optional
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import BaseSpeechToTextProvider
from app.modules.speech.openai_stt_provider import OpenAiSpeechToTextProvider
from app.modules.speech.whisper_stt_provider import LocalWhisperSpeechToTextProvider


class SpeechProviderHub:
    """Manages available Speech-To-Text providers, registering defaults and allowing dynamic switches."""

    def __init__(self) -> None:
        self._providers: Dict[str, BaseSpeechToTextProvider] = {}
        self._register_default_providers()

    def _register_default_providers(self) -> None:
        # Register core out-of-the-box providers
        self.register_provider("whisper", LocalWhisperSpeechToTextProvider())
        self.register_provider("openai", OpenAiSpeechToTextProvider())
        logger.info("SpeechProviderHub initialized with default providers: whisper, openai")

    def register_provider(self, name: str, provider: BaseSpeechToTextProvider) -> None:
        """Allows plugins or developers to register new STT providers."""
        self._providers[name.lower()] = provider
        logger.debug("Registered speech provider: {}", name)

    def get_provider(self, name: str) -> BaseSpeechToTextProvider:
        """Resolves the STT provider class by identifier name."""
        provider = self._providers.get(name.lower())
        if not provider:
            raise ServiceError(
                f"STT provider '{name}' is not registered. "
                f"Available providers are: {', '.join(self.list_providers())}"
            )
        return provider

    def list_providers(self) -> List[str]:
        """Lists names of all registered providers."""
        return list(self._providers.keys())
