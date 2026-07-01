from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Slot
from loguru import logger
import asyncio
from app.application.services.project_service import ProjectService
from app.core.entities.project import Project


class ProjectsViewModel(QObject):
    """ViewModel representing project selection state and creation actions."""

    projects_updated = Signal()
    active_project_changed = Signal(str)  # Project Name

    def __init__(self, service: ProjectService) -> None:
        super().__init__()
        self._service = service
        self.projects_list: List[Project] = []

    def load_projects(self) -> None:
        """Loads available projects synchronously from repository."""
        thread_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(thread_loop)
        try:
            self.projects_list = thread_loop.run_until_complete(self._service.list_projects())
            self.projects_updated.emit()
        except Exception as e:
            logger.error("Failed to load projects list: {}", e)
        finally:
            thread_loop.close()

    @Slot(str, str)
    def create_project(self, name: str, path: str) -> None:
        """Handles creating a new project and sets it active."""
        thread_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(thread_loop)
        try:
            project = thread_loop.run_until_complete(self._service.create_project(name, path))
            self.active_project_changed.emit(project.name)
            self.load_projects()
        except Exception as e:
            logger.error("Failed to create project: {}", e)
        finally:
            thread_loop.close()

    @Slot(int)
    def select_project_index(self, index: int) -> None:
        """Selects a project as active by list index."""
        if 0 <= index < len(self.projects_list):
            project = self.projects_list[index]
            self._service.set_active_project(project)
            self.active_project_changed.emit(project.name)

    @property
    def active_project_name(self) -> str:
        active = self._service.get_active_project()
        return active.name if active else "None (Select/Create a workspace)"
