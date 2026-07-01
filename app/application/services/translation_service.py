import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, List, Optional
from loguru import logger
from app.core.entities.asset import Asset
from app.core.entities.job import Job, JobStep
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import TranscriptionSegment
from app.core.interfaces.repository import AssetRepository, JobRepository
from app.infrastructure.config.settings import SettingsManager
from app.application.services.job_queue import JobQueueManager
from app.modules.translation.translator_hub import TranslatorHub


class TranslationService:
    """Orchestrates translation workflows on subtitle assets."""

    def __init__(
        self,
        translator_hub: TranslatorHub,
        asset_repo: AssetRepository,
        job_repo: JobRepository,
        job_queue: JobQueueManager,
        settings: SettingsManager,
    ) -> None:
        self._translator_hub = translator_hub
        self._asset_repo = asset_repo
        self._job_repo = job_repo
        self._job_queue = job_queue
        self._settings = settings

    def submit_translation_job(
        self,
        project_id: str,
        subtitle_path: str,
        target_lang: str,
        options: dict[str, Any],
        on_completed_ui: Optional[Callable[[str], None]] = None,
        on_failed_ui: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Saves a translation job in DB and Schedules task in JobQueueManager."""
        import uuid
        job_id = str(uuid.uuid4())

        # Setup database job entity
        job_step = JobStep(step_type="translate", status="PENDING", progress=0.0)
        job = Job(
            id=job_id,
            project_id=project_id,
            status="PENDING",
            priority=options.get("priority", 0),
            steps=[job_step],
        )

        translator_name = options.get("provider", "google")
        translator = self._translator_hub.get_translator(translator_name)

        # Resolve credentials if GPT provider chosen
        if translator_name == "gpt":
            options["api_key"] = self._settings.get("api_keys.openai")

        default_storage = self._settings.get("paths.storage_dir", "storage")
        output_dir = Path(options.get("output_dir", str(Path(default_storage) / "subtitles")))

        # Define background QThreadPool workload
        def workload(progress_hook: Callable[[str, float], None]) -> dict[str, Any]:
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)

            try:
                # Save Job status PENDING in DB
                thread_loop.run_until_complete(self._job_repo.save(job))

                progress_hook("parsing", 10.0)
                # 1. Parse subtitle file to TranscriptionSegments
                segments = self.parse_subtitle_file(subtitle_path)

                progress_hook("translating", 30.0)
                # 2. Run translator on segments
                translated_segments = thread_loop.run_until_complete(
                    translator.translate_segments(
                        segments=segments,
                        target_lang=target_lang,
                        source_lang=options.get("source_lang"),
                    )
                )

                progress_hook("exporting", 80.0)
                # 3. Export new subtitle files
                output_dir.mkdir(parents=True, exist_ok=True)
                ext = Path(subtitle_path).suffix or ".srt"
                base_name = Path(subtitle_path).stem
                out_path = output_dir / f"{base_name}_{target_lang}{ext}"

                # Render format based on input extension
                if ext.lower() == ".vtt":
                    content = self.generate_vtt(translated_segments)
                else:
                    content = self.generate_srt(translated_segments)

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # Save Subtitle Asset to DB
                new_asset = Asset(
                    project_id=project_id,
                    name=f"{base_name} ({target_lang} Subtitles)",
                    file_path=str(out_path),
                    asset_type="subtitle",
                    metadata_json=json.dumps({"language": target_lang, "format": ext.lstrip(".")}),
                )
                thread_loop.run_until_complete(self._asset_repo.save(new_asset))

                # Update Job status to COMPLETED
                job.status = "COMPLETED"
                job.completed_at = datetime.now(timezone.utc)
                job.steps[0].status = "COMPLETED"
                job.steps[0].progress = 100.0
                thread_loop.run_until_complete(self._job_repo.save(job))

                return {"output_path": str(out_path)}

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

    def parse_subtitle_file(self, path: str) -> List[TranscriptionSegment]:
        """Parses SRT or VTT subtitle file format into TranscriptionSegments list."""
        if not os.path.exists(path):
            raise ServiceError(f"Subtitle file not found at: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            raise ServiceError(f"Failed to read subtitle file: {e}") from e

        ext = Path(path).suffix.lower()
        if ext == ".vtt":
            return self._parse_vtt(content)
        return self._parse_srt(content)

    def _parse_srt(self, content: str) -> List[TranscriptionSegment]:
        segments = []
        # Standard SRT block regex
        pattern = re.compile(
            r"(\d+)\r?\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\r?\n(.*?)(?=\n\r?\n|\Z)",
            re.DOTALL,
        )
        matches = pattern.findall(content)
        for match in matches:
            idx, start_str, end_str, text_str = match
            start = self._parse_timestamp_to_seconds(start_str.replace(",", "."))
            end = self._parse_timestamp_to_seconds(end_str.replace(",", "."))
            text = " ".join([line.strip() for line in text_str.split("\n") if line.strip()])
            segments.append(TranscriptionSegment(start=start, end=end, text=text))
        return segments

    def _parse_vtt(self, content: str) -> List[TranscriptionSegment]:
        segments = []
        # Strip WEBVTT header
        cleaned = re.sub(r"^WEBVTT\s*", "", content)
        # Match WebVTT timestamps block
        pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\r?\n(.*?)(?=\n\r?\n|\Z)",
            re.DOTALL,
        )
        matches = pattern.findall(cleaned)
        for match in matches:
            start_str, end_str, text_str = match
            start = self._parse_timestamp_to_seconds(start_str)
            end = self._parse_timestamp_to_seconds(end_str)
            text = " ".join([line.strip() for line in text_str.split("\n") if line.strip()])
            segments.append(TranscriptionSegment(start=start, end=end, text=text))
        return segments

    def _parse_timestamp_to_seconds(self, ts: str) -> float:
        parts = ts.split(":")
        h = int(parts[0])
        m = int(parts[1])
        s_parts = parts[2].split(".")
        s = int(s_parts[0])
        ms = int(s_parts[1])
        return h * 3600 + m * 60 + s + ms / 1000.0

    def generate_srt(self, segments: List[TranscriptionSegment]) -> str:
        lines = []
        for i, seg in enumerate(segments, 1):
            lines.append(str(i))
            lines.append(f"{self._format_timestamp_srt(seg.start)} --> {self._format_timestamp_srt(seg.end)}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)

    def generate_vtt(self, segments: List[TranscriptionSegment]) -> str:
        lines = ["WEBVTT", ""]
        for i, seg in enumerate(segments, 1):
            lines.append(f"{self._format_timestamp_vtt(seg.start)} --> {self._format_timestamp_vtt(seg.end)}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)

    def _format_timestamp_srt(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
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
