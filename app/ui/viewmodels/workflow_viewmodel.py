from typing import Any, Dict, List
from PySide6.QtCore import QObject, Signal, Slot
from loguru import logger
from app.application.services.workflow_engine import WorkflowEngine
from app.core.entities.workflow import Workflow, WorkflowNode, WorkflowEdge


class WorkflowViewModel(QObject):
    """ViewModel representing state, layout, and execution tracking for visual workflows."""

    # UI updates communication signals
    workflow_progress = Signal(str, float)  # job_id, overall progress percent
    node_status_changed = Signal(str, str, str)  # job_id, node_id, status ("RUNNING", "COMPLETED", "FAILED")
    node_progress_updated = Signal(str, str, float)  # job_id, node_id, progress percent
    workflow_completed = Signal(str, dict)  # job_id, results dict
    workflow_failed = Signal(str, str)  # job_id, error message

    def __init__(self, engine: WorkflowEngine) -> None:
        super().__init__()
        self._engine = engine
        self.active_jobs: Dict[str, float] = {}

    @Slot(str, object)
    def run_workflow(self, project_id: str, workflow: Workflow) -> str:
        """Triggers execution of the loaded Directed Acyclic Graph."""
        logger.info("Executing visual workflow DAG: {}", workflow.name)

        def handle_node_started(node_id: str) -> None:
            self.node_status_changed.emit(job_id, node_id, "RUNNING")

        def handle_node_progress(node_id: str, percent: float) -> None:
            self.node_progress_updated.emit(job_id, node_id, percent)

        def handle_node_completed(node_id: str, outputs: dict[str, Any]) -> None:
            self.node_status_changed.emit(job_id, node_id, "COMPLETED")

        def handle_workflow_progress(title: str, percent: float) -> None:
            self.active_jobs[job_id] = percent
            self.workflow_progress.emit(job_id, percent)

        def handle_workflow_completed(res: dict[str, Any]) -> None:
            self.active_jobs.pop(job_id, None)
            self.workflow_completed.emit(job_id, res)

        def handle_workflow_failed(err: str) -> None:
            self.active_jobs.pop(job_id, None)
            self.workflow_failed.emit(job_id, err)

        job_id = self._engine.submit_workflow_job(
            project_id=project_id,
            workflow=workflow,
            on_node_started=handle_node_started,
            on_node_progress=handle_node_progress,
            on_node_completed=handle_node_completed,
            on_workflow_completed=handle_workflow_completed,
            on_workflow_failed=handle_workflow_failed,
        )

        self.active_jobs[job_id] = 0.0
        return job_id
