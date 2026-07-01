import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yt_dlp
from loguru import logger

from app.core.exceptions import ServiceError
from app.core.interfaces.downloader import BaseDownloader, DownloadProgress, DownloadResult


class YtDlpDownloader(BaseDownloader):
    """Concrete implementation of BaseDownloader using the yt-dlp library."""

    async def extract_metadata(self, url: str) -> dict[str, Any]:
        """Queries yt-dlp to extract metadata info without downloading the stream.

        Args:
            url: The media stream URL.

        Returns:
            A dictionary containing parsed metadata attributes.
        """
        # Run blocking yt-dlp operations in a thread pool to avoid blocking the event loop
        return await asyncio.to_thread(self._extract_metadata_sync, url)

    def _extract_metadata_sync(self, url: str) -> dict[str, Any]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ServiceError("Failed to extract info: yt-dlp returned empty metadata.")
                return info  # type: ignore[no-any-return]
        except Exception as e:
            logger.error("yt-dlp metadata extraction failed for URL {}: {}", url, e)
            raise ServiceError(f"Metadata extraction failed: {e}") from e

    async def download(
        self,
        url: str,
        output_dir: str,
        options: dict[str, Any],
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        job_id: str = "",
    ) -> DownloadResult:
        """Downloads a video or playlist asynchronously using yt-dlp.

        Args:
            url: The target video/playlist URL.
            output_dir: Output saving folder path.
            options: Custom download parameters (e.g. format resolution, audio-only).
            progress_callback: Progress update callback.
            job_id: Tracking job identifier.
        """
        return await asyncio.to_thread(
            self._download_sync, url, output_dir, options, progress_callback, job_id
        )

    def _download_sync(
        self,
        url: str,
        output_dir: str,
        options: dict[str, Any],
        progress_callback: Callable[[DownloadProgress], None] | None,
        job_id: str,
    ) -> DownloadResult:

        # Convert output directory path
        out_dir = Path(output_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return DownloadResult(
                success=False, error_message=f"Failed to create output folder: {e}"
            )

        # Setup progress hook
        def ytdl_progress_hook(d: dict[str, Any]) -> None:
            if not progress_callback:
                return

            status_str = d.get("status", "extracting")
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            speed = d.get("speed") or 0.0
            eta = d.get("eta") or 0.0

            # Calculate percentage
            percentage = 0.0
            if total > 0:
                percentage = float(downloaded) / float(total) * 100.0
            elif status_str == "finished":
                percentage = 100.0

            # Map status
            status_map = {
                "downloading": "downloading",
                "finished": "completed",
                "error": "failed",
            }
            mapped_status = status_map.get(status_str, "extracting")

            prog = DownloadProgress(
                job_id=job_id,
                url=url,
                status=mapped_status,
                percentage=percentage,
                speed=speed,
                eta=eta,
                downloaded_bytes=downloaded,
                total_bytes=total,
            )
            try:
                progress_callback(prog)
            except Exception as cb_err:
                logger.error("Error invoking progress callback: {}", cb_err)

        # Standard yt-dlp configurations
        # Default save template: output_dir/title.ext
        outtmpl = str(out_dir / "%(title)s.%(ext)s")

        ydl_opts = {
            "outtmpl": outtmpl,
            "progress_hooks": [ytdl_progress_hook],
            "quiet": True,
            "no_warnings": True,
        }

        # Resolve format configurations based on user options
        # Available presets: highest, custom_res, audio_only
        quality = options.get("quality", "highest")
        if quality == "audio_only":
            ydl_opts["format"] = "bestaudio/best"
            # Extract audio to specific formats
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": options.get("audio_codec", "mp3"),
                    "preferredquality": options.get("audio_quality", "192"),
                }
            ]
        elif quality == "custom_res":
            res = options.get("resolution", "1080")
            # Select best video stream equal to or less than resolution and merge with best audio
            ydl_opts["format"] = f"bestvideo[height<={res}]+bestaudio/best[height<={res}]/best"
        else:
            # "highest" quality (default)
            ydl_opts["format"] = "bestvideo+bestaudio/best"

        # Toggles subtitles download if requested
        if options.get("download_subtitles", False):
            ydl_opts["writesubtitles"] = True
            ydl_opts["subtitleslangs"] = options.get("subtitle_langs", ["en"])
            ydl_opts["writeautomaticsub"] = options.get("download_auto_subtitles", False)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    return DownloadResult(
                        success=False, error_message="yt-dlp returned no download metadata."
                    )

                # Retrieve output file path
                # yt-dlp stores output files in the requested 'requested_downloads' or '_filename'
                file_path = ""
                if "requested_downloads" in info and len(info["requested_downloads"]) > 0:
                    file_path = info["requested_downloads"][0].get("filepath", "")
                else:
                    file_path = ydl.prepare_filename(info)

                return DownloadResult(
                    success=True,
                    file_path=file_path,
                    title=info.get("title", ""),
                    thumbnail_url=info.get("thumbnail", ""),
                    duration=float(info.get("duration") or 0.0),
                    width=info.get("width"),
                    height=info.get("height"),
                    file_size=info.get("filesize") or info.get("filesize_approx") or 0,
                )
        except Exception as e:
            logger.error("Download failed for URL {}: {}", url, e)
            return DownloadResult(success=False, error_message=str(e))
