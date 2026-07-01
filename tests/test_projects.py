import pytest
from typing import Any
from unittest.mock import MagicMock
import pytest_asyncio

from app.application.services.project_service import ProjectService
from app.core.entities.project import Project
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.repositories import SqlAlchemyProjectRepository
from app.ui.viewmodels.projects_viewmodel import ProjectsViewModel


@pytest_asyncio.fixture
async def project_service(db_engine: DatabaseEngine) -> ProjectService:
    """Provides a ProjectService connected to test in-memory DB repo."""
    project_repo = SqlAlchemyProjectRepository(db_engine)
    return ProjectService(project_repo)


@pytest.mark.asyncio
async def test_project_service_lifecycle(project_service: ProjectService) -> None:
    """Verifies project workspace creation and active workspace toggling."""
    # List empty initial projects
    initial_list = await project_service.list_projects()
    assert len(initial_list) == 0
    assert project_service.get_active_project() is None

    # Create new project workspace
    p1 = await project_service.create_project("Project Alpha", "/path/alpha")
    assert p1.id is not None
    assert p1.name == "Project Alpha"
    assert p1.path == "/path/alpha"

    # Verify set active workspace
    assert project_service.get_active_project() is p1

    # Create second project workspace
    p2 = await project_service.create_project("Project Beta", "/path/beta")
    assert len(await project_service.list_projects()) == 2

    # Switch active project workspace
    project_service.set_active_project(p1)
    assert project_service.get_active_project() is p1


def test_projects_viewmodel_actions(project_service: ProjectService) -> None:
    """Verifies that ProjectsViewModel dispatches commands and emits updates signals."""
    vm = ProjectsViewModel(project_service)

    active_changed_events = []
    vm.active_project_changed.connect(lambda name: active_changed_events.append(name))

    projects_updated_events = []
    vm.projects_updated.connect(lambda: projects_updated_events.append(True))

    # Create project through VM
    vm.create_project("VM Project", "/vm/path")

    # Assert active changed signal emitted
    assert len(active_changed_events) == 1
    assert active_changed_events[0] == "VM Project"
    assert vm.active_project_name == "VM Project"

    # Assert project load and list size updated
    assert len(vm.projects_list) == 1
    assert vm.projects_list[0].name == "VM Project"
    assert len(projects_updated_events) > 0

    # Select project
    vm.select_project_index(0)
    assert vm.active_project_name == "VM Project"
