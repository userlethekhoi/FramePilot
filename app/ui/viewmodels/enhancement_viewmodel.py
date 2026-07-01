from typing import Any, Dict
from PySide6.QtCore import QObject, Signal, Slot
from loguru import logger
from app.application.services.enhancement_service import EnhancementService


class EnhancementViewModel(QObject):
    """ViewModel representing state, progress, and logs for the AI Enhancement panel."""

    # UI communicating signals
    enhancement_progress = Signal(str, float)  # job_id, progress percent
    enhancement_completed = Signal(str, str)  # job_id, final output file path
    enhancement_failed = Signal(str, str)  # job_id, error message

    def __init__(self, service: EnhancementService) -> None:
        super().__init__()
        self._service = service
        self.active_jobs: Dict[str, float] = {}

    @Slot(str, str, str, dict)
    def start_enhancement(self, project_id: str, input_path: str, task_type: str, options: dict[str, Any]) -> str:
        """Submits background quality enhancement filters task."""
        logger.info("Starting enhancement: {} on: {} (opts: {})", task_type, input_path, options)

        def handle_progress(percent: float) -> None:
            self.active_jobs[job_id] = percent
            self.enhancement_progress.emit(job_id, percent)

        def handle_completed(out_path: str) -> None:
            self.active_jobs.pop(job_id, None)
            self.enhancement_completed.emit(job_id, out_path)

        def handle_failed(err_msg: str) -> None:
            self.active_jobs.pop(job_id, None)
            self.enhancement_failed.emit(job_id, err_msg)

        job_id = self._service.submit_enhancement_job(
            project_id=project_id,
            input_path=input_path,
            task_type=task_type,
            options=options,
            on_progress_ui=handle_progress,
            on_completed_ui=handle_completed,
            on_failed_ui=handle_failed,
        )

        self.active_jobs[job_id] = 0.0
        return job_id
