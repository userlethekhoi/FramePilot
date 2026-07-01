from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class DownloadProgress:
    """Represents real-time telemetry metrics of a media download task."""

    job_id: str
    url: str
    status: str  # extracting, downloading, completed, failed, cancelled
    percentage: float = 0.0
    speed: float = 0.0  # bytes/second
    eta: float = 0.0  # seconds remaining
    downloaded_bytes: int = 0
    total_bytes: int = 0


@dataclass
class DownloadResult:
    """Represents the final completion state and metadata of a download operation."""

    success: bool
    file_path: str = ""
    title: str = ""
    thumbnail_url: str = ""
    duration: float = 0.0
    width: int | None = None
    height: int | None = None
    file_size: int = 0
    error_message: str | None = None


class BaseDownloader(ABC):
    """Abstract interface governing all media extraction and downloader implementations."""

    @abstractmethod
    async def extract_metadata(self, url: str) -> dict[str, Any]:
        """Queries video URL metadata, resolving streams, channels, and sizes without fetching bytes.

        Args:
            url: The media stream URL to query.

        Returns:
            A metadata dictionary containing available formats, titles, and thumbnails.
        """
        pass

    @abstractmethod
    async def download(
        self,
        url: str,
        output_dir: str,
        options: dict[str, Any],
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        job_id: str = "",
    ) -> DownloadResult:
        """Executes a blocking file download operation on the current thread.

        Args:
            url: The media URL to download.
            output_dir: The directory to save the output files.
            options: Custom download parameters (e.g. format resolution, subtitles, audio-only).
            progress_callback: Optional callback reporting DownloadProgress.
            job_id: Optional tracking identifier for progress correlation.

        Returns:
            A DownloadResult containing file location and status.
        """
        pass
