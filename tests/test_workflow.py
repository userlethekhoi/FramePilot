import os
import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest_asyncio

from app.application.services.workflow_engine import WorkflowEngine
from app.application.services.job_queue import JobQueueManager
from app.core.entities.project import Project
from app.core.entities.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.core.exceptions import ServiceError
from app.infrastructure.config.settings import SettingsManager
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProjectRepository,
)


def test_topological_sort_success() -> None:
    """Verifies that dependency graphs sort in order successfully."""
    # Build simple chain: A -> B -> C
    node_a = WorkflowNode("a", "download", "A")
    node_b = WorkflowNode("b", "transcribe", "B")
    node_c = WorkflowNode("c", "translate", "C")
    
    edge1 = WorkflowEdge("e1", "a", "file_path", "b", "file_path")
    edge2 = WorkflowEdge("e2", "b", "subtitles_path", "c", "subtitles_path")

    workflow = Workflow(
        id="w1",
        name="Chain Workflow",
        nodes=[node_a, node_b, node_c],
        edges=[edge1, edge2],
    )

    engine = WorkflowEngine(
        download_service=MagicMock(),
        stt_service=MagicMock(),
        translation_service=MagicMock(),
        tts_service=MagicMock(),
        enhancement_service=MagicMock(),
        asset_repo=MagicMock(),
        job_repo=MagicMock(),
        job_queue=MagicMock(),
        settings=MagicMock(),
    )

    sorted_nodes = engine.topological_sort(workflow)
    assert len(sorted_nodes) == 3
    assert sorted_nodes[0].id == "a"
    assert sorted_nodes[1].id == "b"
    assert sorted_nodes[2].id == "c"


def test_topological_sort_cycle_error() -> None:
    """Verifies that circular references throw clean ValuError."""
    # A -> B -> A
    node_a = WorkflowNode("a", "download", "A")
    node_b = WorkflowNode("b", "transcribe", "B")
    
    edge1 = WorkflowEdge("e1", "a", "file_path", "b", "file_path")
    edge2 = WorkflowEdge("e2", "b", "file_path", "a", "file_path")

    workflow = Workflow(
        id="w_cycle",
        name="Cyclic Workflow",
        nodes=[node_a, node_b],
        edges=[edge1, edge2],
    )

    engine = WorkflowEngine(
        download_service=MagicMock(),
        stt_service=MagicMock(),
        translation_service=MagicMock(),
        tts_service=MagicMock(),
        enhancement_service=MagicMock(),
        asset_repo=MagicMock(),
        job_repo=MagicMock(),
        job_queue=MagicMock(),
        settings=MagicMock(),
    )

    with pytest.raises(ValueError, match="Dependency cycle detected"):
        engine.topological_sort(workflow)


@pytest_asyncio.fixture
async def workflow_engine(
    db_engine: DatabaseEngine,
    settings_manager: SettingsManager,
) -> WorkflowEngine:
    """Provides a WorkflowEngine configured with mock services for integration check."""
    
    # Mock download service
    download_mock = MagicMock()
    # Mock transcribe service
    stt_mock = MagicMock()
    # Mock translation service
    translation_mock = MagicMock()
    # Mock tts service
    tts_mock = MagicMock()
    # Mock enhancement service
    enhance_mock = MagicMock()

    asset_repo = SqlAlchemyAssetRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)
    job_queue = JobQueueManager(max_threads=1)

    return WorkflowEngine(
        download_service=download_mock,
        stt_service=stt_mock,
        translation_service=translation_mock,
        tts_service=tts_mock,
        enhancement_service=enhance_mock,
        asset_repo=asset_repo,
        job_repo=job_repo,
        job_queue=job_queue,
        settings=settings_manager,
    )


@pytest.mark.asyncio
async def test_workflow_engine_execution(
    workflow_engine: WorkflowEngine, db_engine: DatabaseEngine, qtbot: Any
) -> None:
    """Verifies workflow executes step actions, records results and triggers final callback."""
    proj_repo = SqlAlchemyProjectRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)

    # Create dummy project
    project = await proj_repo.save(Project(name="WF Project", path="/tmp"))
    project_id = project.id
    assert project_id is not None

    # Define simple workflow nodes (Translate -> Export)
    node_trans = WorkflowNode(
        id="trans_1",
        node_type="translate",
        title="Translate Subtitles",
        properties={"file_path": "/tmp/mock.srt", "target_lang": "vi", "mock": True},
    )
    node_export = WorkflowNode(
        id="export_1",
        node_type="export",
        title="Export File",
        properties={"destination_path": os.path.join("storage", "exported", "out.srt")},
    )

    # Edge from translate output to export input
    edge = WorkflowEdge("e1", "trans_1", "subtitles_path", "export_1", "file_path")

    workflow = Workflow(
        id="wf_exec_1",
        name="Translate and Export",
        nodes=[node_trans, node_export],
        edges=[edge],
    )

    # Setup translation mock behavior
    def mock_submit_translate(
        project_id: str,
        subtitle_path: str,
        target_lang: str,
        options: dict[str, Any],
        on_completed_ui: Any = None,
        on_failed_ui: Any = None,
    ) -> str:
        # Trigger completed callback inside loop thread
        import tempfile
        from pathlib import Path
        temp_dir = tempfile.gettempdir()
        out_path = str(Path(temp_dir) / "mock_translated.srt")
        with open(out_path, "w") as f:
            f.write("mock translation content")
        if on_completed_ui:
            on_completed_ui(out_path)
        return "job_trans_1"

    setattr(workflow_engine._translation_service, "submit_translation_job", mock_submit_translate)

    completed_events = []

    def on_workflow_completed(res: dict[str, Any]) -> None:
        completed_events.append(res)

    # Submit workflow execution
    job_id = workflow_engine.submit_workflow_job(
        project_id=project_id,
        workflow=workflow,
        on_workflow_completed=on_workflow_completed,
    )

    assert job_id is not None
    qtbot.waitUntil(lambda: len(completed_events) > 0, timeout=4000)

    # Assert final results and exports
    assert len(completed_events) == 1
    res = completed_events[0]
    assert res["workflow_id"] == "wf_exec_1"
    
    # Check export file was created
    expected_export = os.path.join("storage", "exported", "out.srt")
    assert os.path.exists(expected_export)

    # Verify db logs
    db_job = await job_repo.get_by_id(job_id)
    assert db_job is not None
    assert db_job.status == "COMPLETED"
    assert len(db_job.steps) == 2
    assert db_job.steps[0].status == "COMPLETED"
    assert db_job.steps[1].status == "COMPLETED"

    # Clean up generated exports
    if os.path.exists(expected_export):
        os.remove(expected_export)
    export_dir = os.path.join("storage", "exported")
    if os.path.exists(export_dir):
        os.rmdir(export_dir)
