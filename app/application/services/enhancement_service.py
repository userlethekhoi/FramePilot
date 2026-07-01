import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Optional
from loguru import logger
from app.core.entities.asset import Asset
from app.core.entities.job import Job, JobStep
from app.core.interfaces.repository import AssetRepository, JobRepository
from app.infrastructure.config.settings import SettingsManager
from app.application.services.job_queue import JobQueueManager
from app.modules.enhancement.enhancement_hub import EnhancementHub


class EnhancementService:
    """Orchestrates video and image quality enhancement tasks."""

    def __init__(
        self,
        enhancement_hub: EnhancementHub,
        asset_repo: AssetRepository,
        job_repo: JobRepository,
        job_queue: JobQueueManager,
        settings: SettingsManager,
    ) -> None:
        self._enhancement_hub = enhancement_hub
        self._asset_repo = asset_repo
        self._job_repo = job_repo
        self._job_queue = job_queue
        self._settings = settings

    def submit_enhancement_job(
        self,
        project_id: str,
        input_path: str,
        task_type: str,
        options: dict[str, Any],
        on_progress_ui: Optional[Callable[[float], None]] = None,
        on_completed_ui: Optional[Callable[[str], None]] = None,
        on_failed_ui: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Saves an enhancement job in DB and Schedules the filter task in JobQueueManager."""
        import uuid
        job_id = str(uuid.uuid4())

        # Setup database job entity
        job_step = JobStep(step_type=task_type, status="PENDING", progress=0.0)
        job = Job(
            id=job_id,
            project_id=project_id,
            status="PENDING",
            priority=options.get("priority", 0),
            steps=[job_step],
        )

        engine_name = options.get("provider", "ffmpeg")
        enhancer = self._enhancement_hub.get_enhancer(engine_name)

        default_storage = self._settings.get("paths.storage_dir", "storage")
        output_dir = Path(options.get("output_dir", str(Path(default_storage) / "enhanced")))

        # Define background QThreadPool workload
        def workload(progress_hook: Callable[[str, float], None]) -> dict[str, Any]:
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)

            def progress_callback(percent: float) -> None:
                progress_hook(task_type, percent)
                if on_progress_ui:
                    on_progress_ui(percent)

            try:
                # Save Job status PENDING in DB
                thread_loop.run_until_complete(self._job_repo.save(job))

                # Output filename configuration
                output_dir.mkdir(parents=True, exist_ok=True)
                ext = Path(input_path).suffix or ".mp4"
                base_name = Path(input_path).stem
                out_path = output_dir / f"{base_name}_{task_type}{ext}"

                # Run enhancement task blockingly in worker thread
                final_path = thread_loop.run_until_complete(
                    enhancer.enhance(
                        input_path=input_path,
                        output_path=str(out_path),
                        task_type=task_type,
                        options=options,
                        progress_callback=progress_callback,
                    )
                )

                # Save Enhanced Asset references to SQLite
                asset_type = "video" if ext.lower() in [".mp4", ".mkv", ".mov", ".avi"] else "image"
                new_asset = Asset(
                    project_id=project_id,
                    name=f"{base_name} ({task_type} Enhanced)",
                    file_path=final_path,
                    asset_type=asset_type,
                    metadata_json=json.dumps({"filter": task_type, "engine": engine_name}),
                )
                thread_loop.run_until_complete(self._asset_repo.save(new_asset))

                # Update Job status to COMPLETED
                job.status = "COMPLETED"
                job.completed_at = datetime.now(timezone.utc)
                job.steps[0].status = "COMPLETED"
                job.steps[0].progress = 100.0
                thread_loop.run_until_complete(self._job_repo.save(job))

                return {"output_path": final_path}

            except Exception as e:
                # Update Job status to FAILED in DB
                job.status = "FAILED"
                job.steps[0].status = "FAILED"
                job.steps[0].logs = str(e)
                thread_loop.run_until_complete(self._job_repo.save(job))
                raise e
            finally:
                thread_loop.close()

        def handle_completed(jid: str, results: dict[str, Any]) -> None:
            if on_completed_ui:
                on_completed_ui(results["output_path"])

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
