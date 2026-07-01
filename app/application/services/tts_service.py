import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, List, Optional
from loguru import logger
from app.core.entities.asset import Asset
from app.core.entities.job import Job, JobStep
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import TranscriptionSegment
from app.core.interfaces.repository import AssetRepository, JobRepository
from app.infrastructure.config.settings import SettingsManager
from app.application.services.job_queue import JobQueueManager
from app.modules.tts.tts_hub import TextToSpeechHub
from app.application.services.translation_service import TranslationService


class TextToSpeechService:
    """Orchestrates voice synthesis and dubbed audio tracks generation from subtitle segments."""

    def __init__(
        self,
        tts_hub: TextToSpeechHub,
        translation_service: TranslationService,
        asset_repo: AssetRepository,
        job_repo: JobRepository,
        job_queue: JobQueueManager,
        settings: SettingsManager,
    ) -> None:
        self._tts_hub = tts_hub
        self._translation_service = translation_service
        self._asset_repo = asset_repo
        self._job_repo = job_repo
        self._job_queue = job_queue
        self._settings = settings

    def submit_synthesis_job(
        self,
        project_id: str,
        subtitle_path: str,
        voice_id: str,
        options: dict[str, Any],
        on_completed_ui: Optional[Callable[[str], None]] = None,
        on_failed_ui: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Saves a synthesis job in DB and Schedules task in JobQueueManager."""
        import uuid
        job_id = str(uuid.uuid4())

        # Setup database job entity
        job_step = JobStep(step_type="synthesize_audio", status="PENDING", progress=0.0)
        job = Job(
            id=job_id,
            project_id=project_id,
            status="PENDING",
            priority=options.get("priority", 0),
            steps=[job_step],
        )

        engine_name = options.get("provider", "local")
        engine = self._tts_hub.get_engine(engine_name)

        # Resolve credentials if OpenAI chosen
        if engine_name == "openai":
            options["api_key"] = self._settings.get("api_keys.openai")

        default_storage = self._settings.get("paths.storage_dir", "storage")
        output_dir = Path(options.get("output_dir", str(Path(default_storage) / "audio")))

        # Define background QThreadPool workload
        def workload(progress_hook: Callable[[str, float], None]) -> dict[str, Any]:
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)

            try:
                # Save Job status PENDING in DB
                thread_loop.run_until_complete(self._job_repo.save(job))

                progress_hook("parsing", 10.0)
                # 1. Parse subtitle file
                segments = self._translation_service.parse_subtitle_file(subtitle_path)

                progress_hook("synthesizing", 30.0)
                # 2. Synthesize audio segments blockingly inside worker thread
                output_dir.mkdir(parents=True, exist_ok=True)
                dub_dir = output_dir / f"dub_{job_id}"
                
                segment_paths = thread_loop.run_until_complete(
                    engine.synthesize_segments(
                        segments=segments,
                        voice_id=voice_id,
                        output_dir=str(dub_dir),
                        options=options,
                    )
                )

                progress_hook("merging", 80.0)
                # 3. Combine segments into single dubbed audio track
                base_name = Path(subtitle_path).stem
                out_track_path = output_dir / f"{base_name}_dubbed.mp3"
                
                # Call merge utility
                self._merge_audio_segments(segment_paths, segments, str(out_track_path))

                # Save Dubbing Audio Asset to DB
                new_asset = Asset(
                    project_id=project_id,
                    name=f"{base_name} (Dubbed Voice Track)",
                    file_path=str(out_track_path),
                    asset_type="audio",
                    metadata_json=json.dumps({"voice_id": voice_id, "format": "mp3"}),
                )
                thread_loop.run_until_complete(self._asset_repo.save(new_asset))

                # Update Job status to COMPLETED
                job.status = "COMPLETED"
                job.completed_at = datetime.now(timezone.utc)
                job.steps[0].status = "COMPLETED"
                job.steps[0].progress = 100.0
                thread_loop.run_until_complete(self._job_repo.save(job))

                return {"output_path": str(out_track_path)}

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

    def _merge_audio_segments(
        self,
        paths: List[str],
        segments: List[TranscriptionSegment],
        output_path: str,
    ) -> None:
        """Merges multiple timed audio segments aligning them with timestamps."""
        
        # Professional fallback pattern:
        # If pydub is installed, we can align and mix audio precisely.
        # Otherwise, we create a basic concatenated file, or copy the first one.
        try:
            from pydub import AudioSegment
        except ImportError:
            logger.warning("pydub not installed. Writing basic concatenated audio file instead.")
            # Basic raw concatenate fallback
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as outfile:
                    for p in paths:
                        if os.path.exists(p):
                            with open(p, "rb") as infile:
                                outfile.write(infile.read())
                return
            except Exception as e:
                raise ServiceError(f"Fallback audio merge failed: {e}") from e

        try:
            # High-fidelity alignment using pydub
            combined = AudioSegment.silent(duration=int(segments[-1].end * 1000) + 1000)
            
            for path, seg in zip(paths, segments):
                if not os.path.exists(path):
                    continue
                segment_audio = AudioSegment.from_file(path)
                position_ms = int(seg.start * 1000)
                combined = combined.overlay(segment_audio, position=position_ms)
                
            combined.export(output_path, format="mp3")
        except Exception as e:
            logger.error("pydub alignment merge failed: {}. Falling back to raw concatenate.", e)
            # Basic fallback
            with open(output_path, "wb") as outfile:
                for p in paths:
                    with open(p, "rb") as infile:
                        outfile.write(infile.read())
