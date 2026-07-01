import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from app.application.services.job_queue import JobQueueManager
from app.core.entities.asset import Asset
from app.core.entities.job import Job, JobStep
from app.core.exceptions import ServiceError
from app.core.interfaces.downloader import BaseDownloader, DownloadProgress, DownloadResult
from app.core.interfaces.repository import AssetRepository, JobRepository
from app.infrastructure.config.settings import SettingsManager


class DownloadService:
    """Orchestrates video downloads, updates DB states, and Schedules background download tasks."""

    def __init__(
        self,
        downloader: BaseDownloader,
        asset_repo: AssetRepository,
        job_repo: JobRepository,
        job_queue: JobQueueManager,
        settings: SettingsManager,
    ) -> None:
        self._downloader = downloader
        self._asset_repo = asset_repo
        self._job_repo = job_repo
        self._job_queue = job_queue
        self._settings = settings

    async def get_media_info(self, url: str) -> dict[str, Any]:
        """Extracts media metadata (without downloading) for display in the view models."""
        try:
            info = await self._downloader.extract_metadata(url)
            return {
                "title": info.get("title", "Unknown Title"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": float(info.get("duration") or 0.0),
                "uploader": info.get("uploader", ""),
                "formats": [
                    {
                        "format_id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "resolution": f.get("resolution"),
                        "filesize": f.get("filesize") or f.get("filesize_approx") or 0,
                    }
                    for f in info.get("formats", [])
                    if f.get("resolution") and f.get("resolution") != "multiple"
                ],
            }
        except Exception as e:
            logger.error("Failed to fetch media metadata for {}: {}", url, e)
            raise ServiceError(f"Failed to fetch video information: {e}") from e

    def submit_download_job(
        self,
        project_id: str,
        url: str,
        options: dict[str, Any],
        on_progress_ui: Callable[[DownloadProgress], None] | None = None,
        on_completed_ui: Callable[[DownloadResult], None] | None = None,
        on_failed_ui: Callable[[str], None] | None = None,
    ) -> str:
        """Saves a download job state in DB and Schedules download thread execution in JobQueueManager."""

        import uuid
        job_id = str(uuid.uuid4())

        # 1. Setup temporary job model
        job_step = JobStep(step_type="download", status="PENDING", progress=0.0)
        job = Job(
            id=job_id,
            project_id=project_id,
            status="PENDING",
            priority=options.get("priority", 0),
            steps=[job_step],
        )

        # Resolve output directory
        default_dl_dir = self._settings.get("paths.storage_dir", "storage")
        output_dir = options.get("output_dir", str(Path(default_dl_dir) / "downloads"))

        # 2. Define thread workload delegate
        def workload(progress_hook: Callable[[str, float], None]) -> dict[str, Any]:
            # This runs on a separate QThreadPool worker thread
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)

            # Map progress hook to downloader callback
            def download_progress_callback(prog: DownloadProgress) -> None:
                progress_hook(prog.status, prog.percentage)
                if on_progress_ui:
                    on_progress_ui(prog)

            try:
                # Save Job to DB first inside the worker thread
                thread_loop.run_until_complete(self._job_repo.save(job))

                # Run the async downloader blockingly inside worker thread
                result = thread_loop.run_until_complete(
                    self._downloader.download(
                        url=url,
                        output_dir=output_dir,
                        options=options,
                        progress_callback=download_progress_callback,
                        job_id=job_id,
                    )
                )

                if result.success:
                    # Register asset to database
                    asset = Asset(
                        project_id=project_id,
                        name=result.title or Path(result.file_path).name,
                        file_path=result.file_path,
                        asset_type="video" if options.get("quality") != "audio_only" else "audio",
                        metadata_json=json.dumps(
                            {
                                "duration": result.duration,
                                "width": result.width,
                                "height": result.height,
                                "file_size": result.file_size,
                            }
                        ),
                    )
                    thread_loop.run_until_complete(self._asset_repo.save(asset))

                    # Update Job status to COMPLETED
                    job.status = "COMPLETED"
                    job.completed_at = datetime.now(UTC)
                    job.steps[0].status = "COMPLETED"
                    job.steps[0].progress = 100.0
                    thread_loop.run_until_complete(self._job_repo.save(job))

                    return {"result": result}
                raise ServiceError(result.error_message or "Unknown download error")
            except Exception as e:
                # Update Job status to FAILED in DB
                job.status = "FAILED"
                job.steps[0].status = "FAILED"
                job.steps[0].logs = str(e)
                thread_loop.run_until_complete(self._job_repo.save(job))
                raise e
            finally:
                thread_loop.close()

        # 3. Schedule execution on threadpool
        def handle_completed(jid: str, results: dict[str, Any]) -> None:
            if on_completed_ui:
                on_completed_ui(results["result"])

        def handle_failed(jid: str, err: str) -> None:
            if on_failed_ui:
                on_failed_ui(err)

        self._job_queue.submit(
            job_id=job_id,
            workload_fn=workload,
            on_completed=handle_completed,
            on_failed=handle_failed,
        )

        return job_id
