import asyncio
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional
from loguru import logger
from app.core.entities.asset import Asset
from app.core.entities.job import Job, JobStep
from app.core.entities.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.core.exceptions import ServiceError
from app.core.interfaces.repository import AssetRepository, JobRepository
from app.infrastructure.config.settings import SettingsManager
from app.application.services.job_queue import JobQueueManager
from app.application.services.download_service import DownloadService
from app.application.services.stt_service import SpeechToTextService
from app.application.services.translation_service import TranslationService
from app.application.services.tts_service import TextToSpeechService
from app.application.services.enhancement_service import EnhancementService


class WorkflowEngine:
    """Executes Directed Acyclic Graph (DAG) workflows of chained media processing tasks."""

    def __init__(
        self,
        download_service: DownloadService,
        stt_service: SpeechToTextService,
        translation_service: TranslationService,
        tts_service: TextToSpeechService,
        enhancement_service: EnhancementService,
        asset_repo: AssetRepository,
        job_repo: JobRepository,
        job_queue: JobQueueManager,
        settings: SettingsManager,
    ) -> None:
        self._download_service = download_service
        self._stt_service = stt_service
        self._translation_service = translation_service
        self._tts_service = tts_service
        self._enhancement_service = enhancement_service
        self._asset_repo = asset_repo
        self._job_repo = job_repo
        self._job_queue = job_queue
        self._settings = settings

    def submit_workflow_job(
        self,
        project_id: str,
        workflow: Workflow,
        on_node_started: Optional[Callable[[str], None]] = None,
        on_node_progress: Optional[Callable[[str, float], None]] = None,
        on_node_completed: Optional[Callable[[str, dict[str, Any]], None]] = None,
        on_workflow_completed: Optional[Callable[[dict[str, Any]], None]] = None,
        on_workflow_failed: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Saves a workflow job in DB and Schedules sequential nodes execution in JobQueueManager."""
        import uuid
        job_id = str(uuid.uuid4())

        # Build topological sort to determine node execution order & detect cycles
        try:
            execution_order = self.topological_sort(workflow)
        except Exception as e:
            raise ServiceError(f"Invalid workflow graph: {e}") from e

        # Setup database job entity with steps for each node in order
        steps = []
        for node in execution_order:
            steps.append(JobStep(step_type=node.node_type, status="PENDING", progress=0.0, logs=node.title))
            
        job = Job(
            id=job_id,
            project_id=project_id,
            status="PENDING",
            priority=1,
            steps=steps,
        )

        # Define background QThreadPool workload
        def workload(progress_hook: Callable[[str, float], None]) -> dict[str, Any]:
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)

            try:
                # Save Job status PENDING in DB
                thread_loop.run_until_complete(self._job_repo.save(job))
                
                # Dictionary storing outputs of each completed node: node_id -> {port_name: value}
                results: Dict[str, Dict[str, Any]] = {}

                # Execute nodes in topological order
                for step_idx, node in enumerate(execution_order):
                    node.status = "RUNNING"
                    node.progress = 0.0
                    if on_node_started:
                        on_node_started(node.id)

                    # Update database step to RUNNING
                    job.steps[step_idx].status = "RUNNING"
                    thread_loop.run_until_complete(self._job_repo.save(job))

                    # 1. Resolve inputs from upstream edges
                    inputs = self._resolve_node_inputs(node, workflow.edges, results)

                    # 2. Execute node task blockingly
                    node_outputs = thread_loop.run_until_complete(
                        self._execute_node(project_id, node, inputs, on_node_progress)
                    )

                    # Store results
                    results[node.id] = node_outputs
                    node.status = "COMPLETED"
                    node.progress = 100.0
                    if on_node_completed:
                        on_node_completed(node.id, node_outputs)

                    # Update database step to COMPLETED
                    job.steps[step_idx].status = "COMPLETED"
                    job.steps[step_idx].progress = 100.0
                    thread_loop.run_until_complete(self._job_repo.save(job))

                    # Update overall workflow job progress
                    overall_progress = ((step_idx + 1) / len(execution_order)) * 100.0
                    progress_hook(node.title, overall_progress)

                # Update Job status to COMPLETED
                job.status = "COMPLETED"
                job.completed_at = datetime.now(timezone.utc)
                thread_loop.run_until_complete(self._job_repo.save(job))

                return {"workflow_id": workflow.id, "results": results}

            except Exception as e:
                # Update Job status to FAILED in DB
                job.status = "FAILED"
                # Mark current step as FAILED
                for step in job.steps:
                    if step.status == "RUNNING" or step.status == "PENDING":
                        step.status = "FAILED"
                        step.logs = str(e)
                        break
                thread_loop.run_until_complete(self._job_repo.save(job))
                raise e
            finally:
                thread_loop.close()

        def handle_completed(jid: str, results: dict[str, Any]) -> None:
            if on_workflow_completed:
                on_workflow_completed(results)

        def handle_failed(jid: str, err: str) -> None:
            if on_workflow_failed:
                on_workflow_failed(err)

        self._job_queue.submit(
            job_id=job_id,
            workload_fn=workload,
            on_completed=handle_completed,
            on_failed=handle_failed,
        )

        return job_id

    def topological_sort(self, workflow: Workflow) -> List[WorkflowNode]:
        """Calculates topological sorting of the graph and raises error if cycle found."""
        # 1. Build adjacency list and compute in-degrees
        adj: Dict[str, List[str]] = {node.id: [] for node in workflow.nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in workflow.nodes}

        for edge in workflow.edges:
            if edge.source_node_id in adj and edge.target_node_id in in_degree:
                adj[edge.source_node_id].append(edge.target_node_id)
                in_degree[edge.target_node_id] += 1

        # 2. Run Kahn's algorithm
        queue = deque([node_id for node_id, deg in in_degree.items() if deg == 0])
        order_ids = []

        while queue:
            curr = queue.popleft()
            order_ids.append(curr)

            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order_ids) != len(workflow.nodes):
            raise ValueError("Dependency cycle detected in workflow nodes connections.")

        # Map back to WorkflowNode objects
        node_map = {node.id: node for node in workflow.nodes}
        return [node_map[nid] for nid in order_ids]

    def _resolve_node_inputs(self, node: WorkflowNode, edges: List[WorkflowEdge], results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Looks up inputs bound to upstream outputs."""
        inputs = {}
        # Load default properties first
        for k, v in node.properties.items():
            inputs[k] = v

        # Overlay connected edges
        for edge in edges:
            if edge.target_node_id == node.id:
                source_res = results.get(edge.source_node_id, {})
                output_val = source_res.get(edge.source_port)
                if output_val is not None:
                    # Dynamically bind to input port name
                    inputs[edge.target_port] = output_val
                    
        return inputs

    async def _execute_node(
        self,
        project_id: str,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        on_node_progress: Optional[Callable[[str, float], None]],
    ) -> Dict[str, Any]:
        """Invokes the appropriate service to execute the task block synchronously/asynchronously."""
        logger.info("Executing node: {} ({}) with inputs: {}", node.id, node.node_type, inputs)

        # Set up a helper future to block until the service completes
        future: Any = asyncio.get_event_loop().create_future()

        def progress_callback(percent: float) -> None:
            node.progress = percent
            if on_node_progress:
                on_node_progress(node.id, percent)

        # 1. DOWNLOAD NODE
        if node.node_type == "download":
            url = inputs.get("url")
            if not url:
                raise ValueError("Missing 'url' parameter for Download node.")

            self._download_service.submit_download_job(
                project_id=project_id,
                url=url,
                options=inputs,
                on_progress_ui=lambda prog: progress_callback(prog.percentage),
                on_completed_ui=lambda res: future.set_result({"file_path": res.file_path}),
                on_failed_ui=lambda err: future.set_exception(Exception(err)),
            )

        # 2. TRANSCRIBE NODE
        elif node.node_type == "transcribe":
            media_path = inputs.get("media_path") or inputs.get("file_path")
            if not media_path:
                raise ValueError("Missing 'media_path' / 'file_path' for Transcribe node.")

            self._stt_service.submit_transcribe_job(
                project_id=project_id,
                media_path=media_path,
                options=inputs,
                on_progress_ui=progress_callback,
                on_completed_ui=lambda res: future.set_result({
                    "full_text": res.full_text,
                    "subtitles_path": os.path.join("storage", "subtitles", f"{Path(media_path).stem}.srt")
                }),
                on_failed_ui=lambda err: future.set_exception(Exception(err)),
            )

        # 3. TRANSLATE NODE
        elif node.node_type == "translate":
            sub_path = inputs.get("subtitles_path") or inputs.get("file_path")
            target_lang = inputs.get("target_lang", "vi")
            if not sub_path:
                raise ValueError("Missing 'subtitles_path' / 'file_path' for Translate node.")

            self._translation_service.submit_translation_job(
                project_id=project_id,
                subtitle_path=sub_path,
                target_lang=target_lang,
                options=inputs,
                on_completed_ui=lambda out: future.set_result({"subtitles_path": out}),
                on_failed_ui=lambda err: future.set_exception(Exception(err)),
            )

        # 4. TTS DUBBING NODE
        elif node.node_type == "tts":
            sub_path = inputs.get("subtitles_path") or inputs.get("file_path")
            voice_id = inputs.get("voice_id", "alloy")
            if not sub_path:
                raise ValueError("Missing 'subtitles_path' for TTS node.")

            self._tts_service.submit_synthesis_job(
                project_id=project_id,
                subtitle_path=sub_path,
                voice_id=voice_id,
                options=inputs,
                on_completed_ui=lambda out: future.set_result({"audio_path": out}),
                on_failed_ui=lambda err: future.set_exception(Exception(err)),
            )

        # 5. ENHANCE NODE
        elif node.node_type == "enhance":
            file_path = inputs.get("file_path") or inputs.get("media_path")
            task_type = inputs.get("task_type", "upscale")
            if not file_path:
                raise ValueError("Missing 'file_path' for Enhance node.")

            self._enhancement_service.submit_enhancement_job(
                project_id=project_id,
                input_path=file_path,
                task_type=task_type,
                options=inputs,
                on_progress_ui=progress_callback,
                on_completed_ui=lambda out: future.set_result({"file_path": out}),
                on_failed_ui=lambda err: future.set_exception(Exception(err)),
            )

        # 6. EXPORT NODE
        elif node.node_type == "export":
            src = inputs.get("file_path") or inputs.get("audio_path") or inputs.get("subtitles_path")
            dest = inputs.get("destination_path")
            if not src or not dest:
                raise ValueError("Missing 'file_path' or 'destination_path' for Export node.")

            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                future.set_result({"output_path": dest})
            except Exception as e:
                future.set_exception(e)

        else:
            raise ValueError(f"Unsupported node type: {node.node_type}")

        # Wait for the service callback to set the future result
        res = await future
        if isinstance(res, dict):
            return res
        return {}
