from typing import Any, Dict, List
from PySide6.QtCore import QObject, Signal, Slot
from loguru import logger
from app.application.services.stt_service import SpeechToTextService
from app.core.interfaces.speech import TranscriptionResult


class SpeechToTextViewModel(QObject):
    """ViewModel representing state, progress, and logs for the speech recognition interface."""

    # UI updates communication signals
    transcription_progress = Signal(str, float)  # job_id, progress percentage
    transcription_completed = Signal(str, dict)  # job_id, result_summary
    transcription_failed = Signal(str, str)  # job_id, error_msg

    def __init__(self, stt_service: SpeechToTextService) -> None:
        super().__init__()
        self._service = stt_service
        self.active_jobs: Dict[str, float] = {}

    @Slot(str, str, dict)
    def start_transcription(self, project_id: str, media_path: str, options: dict[str, Any]) -> str:
        """Triggers a background STT job and setups state tracking listeners."""
        logger.info("Triggering transcription for: {} (options: {})", media_path, options)

        def handle_progress(percent: float) -> None:
            self.active_jobs[job_id] = percent
            self.transcription_progress.emit(job_id, percent)

        def handle_completed(res: TranscriptionResult) -> None:
            self.active_jobs.pop(job_id, None)
            
            # Pack summary info for UI display
            summary = {
                "full_text": res.full_text,
                "language": res.language,
                "duration": res.duration,
                "segments_count": len(res.segments),
            }
            self.transcription_completed.emit(job_id, summary)

        def handle_failed(err_msg: str) -> None:
            self.active_jobs.pop(job_id, None)
            self.transcription_failed.emit(job_id, err_msg)

        job_id = self._service.submit_transcribe_job(
            project_id=project_id,
            media_path=media_path,
            options=options,
            on_progress_ui=handle_progress,
            on_completed_ui=handle_completed,
            on_failed_ui=handle_failed,
        )

        self.active_jobs[job_id] = 0.0
        return job_id
