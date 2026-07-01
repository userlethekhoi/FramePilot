from typing import Dict, List
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.translation import BaseTranslator
from app.modules.translation.google_translator import GoogleTranslator
from app.modules.translation.gpt_translator import GptTranslator


class TranslatorHub:
    """Manages active translation engines, supporting Google and GPT clouds."""

    def __init__(self) -> None:
        self._translators: Dict[str, BaseTranslator] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_translator("google", GoogleTranslator())
        self.register_translator("gpt", GptTranslator())
        logger.info("TranslatorHub initialized with default engines: google, gpt")

    def register_translator(self, name: str, translator: BaseTranslator) -> None:
        """Permits registering dynamic custom or plugin translators."""
        self._translators[name.lower()] = translator
        logger.debug("Registered translator engine: {}", name)

    def get_translator(self, name: str) -> BaseTranslator:
        """Retrieves registered translator engine class by name."""
        engine = self._translators.get(name.lower())
        if not engine:
            raise ServiceError(
                f"Translation engine '{name}' is not registered. "
                f"Registered engines: {', '.join(self.list_translators())}"
            )
        return engine

    def list_translators(self) -> List[str]:
        """Lists registered translator names."""
        return list(self._translators.keys())
