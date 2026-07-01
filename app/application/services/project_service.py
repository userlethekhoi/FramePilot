import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from loguru import logger
from app.core.entities.project import Project
from app.core.interfaces.repository import ProjectRepository


class ProjectService:
    """Manages creation, selection, and retrieval of user workspaces (Projects)."""

    def __init__(self, project_repo: ProjectRepository) -> None:
        self._project_repo = project_repo
        self._active_project: Optional[Project] = None

    async def create_project(self, name: str, path: str) -> Project:
        """Creates a new project workspace and registers it in database."""
        logger.info("Creating new project workspace: {} at: {}", name, path)
        project = Project(
            name=name,
            path=path,
            created_at=datetime.now(timezone.utc),
        )
        saved_project = await self._project_repo.save(project)
        self._active_project = saved_project
        return saved_project

    async def list_projects(self) -> List[Project]:
        """Lists all registered project workspaces in the system."""
        return await self._project_repo.list_all()

    def get_active_project(self) -> Optional[Project]:
        """Retrieves currently active project workspace."""
        return self._active_project

    def set_active_project(self, project: Project) -> None:
        """Sets the active project workspace."""
        self._active_project = project
        logger.info("Active workspace switched to: {}", project.name)
