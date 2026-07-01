from typing import Dict, List
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.enhancement import BaseEnhancer
from app.modules.enhancement.ffmpeg_enhancer import FfmpegEnhancer


class EnhancementHub:
    """Manages active image and video enhancement filters engines."""

    def __init__(self) -> None:
        self._enhancers: Dict[str, BaseEnhancer] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_enhancer("ffmpeg", FfmpegEnhancer())
        logger.info("EnhancementHub initialized with default engines: ffmpeg")

    def register_enhancer(self, name: str, enhancer: BaseEnhancer) -> None:
        """Permits registering dynamic custom AI or plugin filters."""
        self._enhancers[name.lower()] = enhancer
        logger.debug("Registered enhancement filter: {}", name)

    def get_enhancer(self, name: str) -> BaseEnhancer:
        """Retrieves registered enhancer class by identifier."""
        engine = self._enhancers.get(name.lower())
        if not engine:
            raise ServiceError(
                f"Enhancement engine '{name}' is not registered. "
                f"Available engines: {', '.join(self.list_enhancers())}"
            )
        return engine

    def list_enhancers(self) -> List[str]:
        """Lists registered enhancer names."""
        return list(self._enhancers.keys())
