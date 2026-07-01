from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Signal, Slot

from app.application.services.download_service import DownloadService
from app.application.services.job_queue import JobQueueManager
from app.core.interfaces.downloader import DownloadProgress, DownloadResult


class DownloaderViewModel(QObject):
    """ViewModel representing state, options, and history for the video download interface."""

    # UI updates communication signals
    info_extracted = Signal(dict)
    info_failed = Signal(str)
    download_progress = Signal(str, float, float, float)  # job_id, percentage, speed, eta
    download_completed = Signal(str, str)  # job_id, file_path
    download_failed = Signal(str, str)  # job_id, error_msg

    def __init__(self, download_service: DownloadService, job_queue: JobQueueManager) -> None:
        super().__init__()
        self._service = download_service
        self._queue = job_queue

        # State representations
        self.active_downloads: dict[str, dict[str, Any]] = {}
        self.download_history: list[dict[str, Any]] = []

    @Slot(str)
    def fetch_video_info(self, url: str) -> None:
        """Fetches metadata details for a URL in a separate worker thread to prevent GUI lagging."""
        logger.info("Requesting metadata extraction for: {}", url)

        # Create a lightweight workload for info extraction
        def workload(progress_hook: Any) -> dict[str, Any]:
            # Run async function blockingly in the worker thread
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                info = loop.run_until_complete(self._service.get_media_info(url))
                return {"info": info}
            finally:
                loop.close()

        def handle_completed(jid: str, result: dict[str, Any]) -> None:
            self.info_extracted.emit(result["info"])

        def handle_failed(jid: str, err: str) -> None:
            self.info_failed.emit(err)

        # Submit query job
        self._queue.submit(
            job_id=f"info_{hash(url)}",
            workload_fn=workload,
            on_completed=handle_completed,
            on_failed=handle_failed,
        )

    @Slot(str, str, dict)
    def trigger_download(self, project_id: str, url: str, options: dict[str, Any]) -> str:
        """Triggers a download job in the background and sets up status tracking listeners."""
        logger.info("Triggering download job for: {} (options: {})", url, options)

        def handle_progress(prog: DownloadProgress) -> None:
            # Store active state
            self.active_downloads[prog.job_id] = {
                "url": prog.url,
                "percentage": prog.percentage,
                "speed": prog.speed,
                "eta": prog.eta,
                "status": prog.status,
            }
            # Emit updates to the View
            self.download_progress.emit(prog.job_id, prog.percentage, prog.speed, prog.eta)

        def handle_completed(res: DownloadResult) -> None:
            # Move from active to history
            self.active_downloads.pop(res.file_path, {})
            history_item = {
                "title": res.title,
                "file_path": res.file_path,
                "duration": res.duration,
                "file_size": res.file_size,
                "downloaded_at": str(type(self).__name__),
            }
            self.download_history.append(history_item)

            # Locate corresponding job_id and notify
            for jid, d in list(self.active_downloads.items()):
                if d.get("url") == url:
                    self.active_downloads.pop(jid, None)
                    self.download_completed.emit(jid, res.file_path)
                    break

        def handle_failed(err_msg: str) -> None:
            # Find and fail active job
            for jid, d in list(self.active_downloads.items()):
                if d.get("url") == url:
                    self.active_downloads.pop(jid, None)
                    self.download_failed.emit(jid, err_msg)
                    break

        job_id = self._service.submit_download_job(
            project_id=project_id,
            url=url,
            options=options,
            on_progress_ui=handle_progress,
            on_completed_ui=handle_completed,
            on_failed_ui=handle_failed,
        )

        self.active_downloads[job_id] = {
            "url": url,
            "percentage": 0.0,
            "speed": 0.0,
            "eta": 0.0,
            "status": "extracting",
        }
        return job_id
