from typing import Any, Dict, List
from PySide6.QtCore import QObject, Signal, Slot
from loguru import logger
from app.application.services.stt_service import SpeechToTextService
from app.application.services.translation_service import TranslationService
from app.application.services.tts_service import TextToSpeechService
from app.core.interfaces.speech import TranscriptionResult


class SpeechToTextViewModel(QObject):
    """ViewModel representing state, progress, and logs for the speech recognition interface."""

    # UI updates communication signals
    transcription_progress = Signal(str, float)  # job_id, progress percentage
    transcription_completed = Signal(str, dict)  # job_id, result_summary
    transcription_failed = Signal(str, str)  # job_id, error_msg

    translation_progress = Signal(str, float)
    translation_completed = Signal(str, str)  # job_id, output_path
    translation_failed = Signal(str, str)

    synthesis_progress = Signal(str, float)
    synthesis_completed = Signal(str, str)  # job_id, output_path
    synthesis_failed = Signal(str, str)

    def __init__(
        self,
        stt_service: SpeechToTextService,
        translation_service: TranslationService,
        tts_service: TextToSpeechService,
    ) -> None:
        super().__init__()
        self._stt_service = stt_service
        self._translation_service = translation_service
        self._tts_service = tts_service
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

        job_id = self._stt_service.submit_transcribe_job(
            project_id=project_id,
            media_path=media_path,
            options=options,
            on_progress_ui=handle_progress,
            on_completed_ui=handle_completed,
            on_failed_ui=handle_failed,
        )

        self.active_jobs[job_id] = 0.0
        return job_id

    @Slot(str, str, str, dict)
    def translate_subtitles(
        self, project_id: str, subtitle_path: str, target_lang: str, options: dict[str, Any]
    ) -> str:
        """Triggers background subtitle translation task."""
        logger.info("Triggering translation to {} for: {}", target_lang, subtitle_path)

        def handle_progress(step_type: str, percent: float) -> None:
            self.active_jobs[job_id] = percent
            self.translation_progress.emit(job_id, percent)

        def handle_completed(output_path: str) -> None:
            self.active_jobs.pop(job_id, None)
            self.translation_completed.emit(job_id, output_path)

        def handle_failed(err_msg: str) -> None:
            self.active_jobs.pop(job_id, None)
            self.translation_failed.emit(job_id, err_msg)

        # Options dictionary can define translation provider (google / gpt)
        options["priority"] = 1
        job_id = self._translation_service.submit_translation_job(
            project_id=project_id,
            subtitle_path=subtitle_path,
            target_lang=target_lang,
            options=options,
            on_completed_ui=handle_completed,
            on_failed_ui=handle_failed,
        )
        
        self.active_jobs[job_id] = 0.0
        return job_id

    @Slot(str, str, str, dict)
    def synthesize_voice(
        self, project_id: str, subtitle_path: str, voice_id: str, options: dict[str, Any]
    ) -> str:
        """Triggers background TTS voice dubbing task."""
        logger.info("Triggering voice synthesis with voice {} for: {}", voice_id, subtitle_path)

        def handle_progress(step_type: str, percent: float) -> None:
            self.active_jobs[job_id] = percent
            self.synthesis_progress.emit(job_id, percent)

        def handle_completed(output_path: str) -> None:
            self.active_jobs.pop(job_id, None)
            self.synthesis_completed.emit(job_id, output_path)

        def handle_failed(err_msg: str) -> None:
            self.active_jobs.pop(job_id, None)
            self.synthesis_failed.emit(job_id, err_msg)

        job_id = self._tts_service.submit_synthesis_job(
            project_id=project_id,
            subtitle_path=subtitle_path,
            voice_id=voice_id,
            options=options,
            on_completed_ui=handle_completed,
            on_failed_ui=handle_failed,
        )

        self.active_jobs[job_id] = 0.0
        return job_id
