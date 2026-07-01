import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, List, Optional
from loguru import logger
from app.core.entities.asset import Asset
from app.core.entities.job import Job, JobStep
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import TranscriptionResult, TranscriptionSegment
from app.core.interfaces.repository import AssetRepository, JobRepository
from app.infrastructure.config.settings import SettingsManager
from app.application.services.job_queue import JobQueueManager
from app.modules.speech.provider_hub import SpeechProviderHub


class SpeechToTextService:
    """Orchestrates speech-to-text processes, exports subtitles formats, and updates job logs."""

    def __init__(
        self,
        provider_hub: SpeechProviderHub,
        asset_repo: AssetRepository,
        job_repo: JobRepository,
        job_queue: JobQueueManager,
        settings: SettingsManager,
    ) -> None:
        self._provider_hub = provider_hub
        self._asset_repo = asset_repo
        self._job_repo = job_repo
        self._job_queue = job_queue
        self._settings = settings

    def submit_transcribe_job(
        self,
        project_id: str,
        media_path: str,
        options: dict[str, Any],
        on_progress_ui: Optional[Callable[[float], None]] = None,
        on_completed_ui: Optional[Callable[[TranscriptionResult], None]] = None,
        on_failed_ui: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Saves a transcription job in DB and Schedules STT thread execution in JobQueueManager."""
        import uuid
        job_id = str(uuid.uuid4())

        # Setup database job entity
        job_step = JobStep(step_type="transcribe", status="PENDING", progress=0.0)
        job = Job(
            id=job_id,
            project_id=project_id,
            status="PENDING",
            priority=options.get("priority", 0),
            steps=[job_step],
        )

        provider_name = options.get("provider", "whisper")
        provider = self._provider_hub.get_provider(provider_name)

        # Resolve credentials if cloud provider chosen
        if provider_name == "openai":
            options["api_key"] = self._settings.get("api_keys.openai")

        # Resolve subtitle save locations
        default_storage = self._settings.get("paths.storage_dir", "storage")
        output_dir = Path(options.get("output_dir", str(Path(default_storage) / "subtitles")))

        # Define background QThreadPool workload
        def workload(progress_hook: Callable[[str, float], None]) -> dict[str, Any]:
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)

            def progress_callback(percentage: float) -> None:
                progress_hook("transcribing", percentage)
                if on_progress_ui:
                    on_progress_ui(percentage)

            try:
                # Save Job status PENDING in DB
                thread_loop.run_until_complete(self._job_repo.save(job))

                # Execute STT transcription in threadpool
                result = thread_loop.run_until_complete(
                    provider.transcribe(
                        audio_path=media_path,
                        options=options,
                        progress_callback=progress_callback,
                    )
                )

                # Export SRT and VTT subtitle files
                output_dir.mkdir(parents=True, exist_ok=True)
                base_name = Path(media_path).stem
                
                srt_content = self.generate_srt(result.segments)
                vtt_content = self.generate_vtt(result.segments)
                txt_content = result.full_text

                srt_path = output_dir / f"{base_name}.srt"
                vtt_path = output_dir / f"{base_name}.vtt"
                txt_path = output_dir / f"{base_name}.txt"

                # Write files blockingly in worker thread
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                with open(vtt_path, "w", encoding="utf-8") as f:
                    f.write(vtt_content)
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(txt_content)

                # Save Subtitle Asset references to Database
                srt_asset = Asset(
                    project_id=project_id,
                    name=f"{base_name} (SRT Subtitles)",
                    file_path=str(srt_path),
                    asset_type="subtitle",
                    metadata_json=json.dumps({"language": result.language, "format": "srt"}),
                )
                thread_loop.run_until_complete(self._asset_repo.save(srt_asset))

                # Update Job status to COMPLETED
                job.status = "COMPLETED"
                job.completed_at = datetime.now(timezone.utc)
                job.steps[0].status = "COMPLETED"
                job.steps[0].progress = 100.0
                thread_loop.run_until_complete(self._job_repo.save(job))

                return {"result": result}

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
                on_completed_ui(results["result"])

        def handle_failed(jid: str, err: str) -> None:
            if on_failed_ui:
                on_failed_ui(err)

        # Submit to background queue
        self._job_queue.submit(
            job_id=job_id,
            workload_fn=workload,
            on_completed=handle_completed,
            on_failed=handle_failed,
        )

        return job_id

    def generate_srt(self, segments: List[TranscriptionSegment]) -> str:
        """Utility to format segments into SubRip (SRT) format."""
        lines = []
        for i, seg in enumerate(segments, 1):
            lines.append(str(i))
            time_range = f"{self._format_timestamp_srt(seg.start)} --> {self._format_timestamp_srt(seg.end)}"
            lines.append(time_range)
            lines.append(seg.text)
            lines.append("")  # Empty spacing between entries
        return "\n".join(lines)

    def generate_vtt(self, segments: List[TranscriptionSegment]) -> str:
        """Utility to format segments into WebVTT (VTT) format."""
        lines = ["WEBVTT", ""]
        for i, seg in enumerate(segments, 1):
            time_range = f"{self._format_timestamp_vtt(seg.start)} --> {self._format_timestamp_vtt(seg.end)}"
            lines.append(time_range)
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)

    def _format_timestamp_srt(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        # Ensure correct bounding
        if ms >= 1000:
            ms = 999
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        if ms >= 1000:
            ms = 999
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
