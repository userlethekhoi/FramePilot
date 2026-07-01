from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Optional


class BaseEnhancer(ABC):
    """Abstract interface governing all local and cloud AI video/image quality enhancement engines."""

    @abstractmethod
    async def enhance(
        self,
        input_path: str,
        output_path: str,
        task_type: str,  # "upscale", "denoise", "fps_adjust", "resize"
        options: dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> str:
        """Runs the quality enhancement filter on a background worker thread.
        
        Args:
            input_path: Path to the local input file (video or image).
            output_path: Target path to write the enhanced output.
            task_type: Type of filter to run (upscale, denoise, fps_adjust, resize).
            options: Filter options (e.g. scale scale, fps count, denoise strength).
            progress_callback: Callback receiving progress float percentage (0.0 to 100.0).
            
        Returns:
            The path to the enhanced output file.
        """
        pass
