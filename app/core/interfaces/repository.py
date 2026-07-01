from abc import ABC, abstractmethod

from app.core.entities.asset import Asset
from app.core.entities.job import Job
from app.core.entities.preset import Preset
from app.core.entities.project import Project


class ProjectRepository(ABC):
    """Abstract interface for project data operations."""

    @abstractmethod
    async def save(self, project: Project) -> Project:
        """Saves a project (creates new or updates existing)."""
        pass

    @abstractmethod
    async def get_by_id(self, project_id: str) -> Project | None:
        """Retrieves a project by its unique ID."""
        pass

    @abstractmethod
    async def list_all(self) -> list[Project]:
        """Lists all existing projects."""
        pass

    @abstractmethod
    async def delete(self, project_id: str) -> bool:
        """Deletes a project by its unique ID."""
        pass


class AssetRepository(ABC):
    """Abstract interface for asset data operations."""

    @abstractmethod
    async def save(self, asset: Asset) -> Asset:
        """Saves an asset."""
        pass

    @abstractmethod
    async def get_by_id(self, asset_id: str) -> Asset | None:
        """Retrieves an asset by its unique ID."""
        pass

    @abstractmethod
    async def list_by_project(self, project_id: str) -> list[Asset]:
        """Lists all assets associated with a specific project."""
        pass

    @abstractmethod
    async def delete(self, asset_id: str) -> bool:
        """Deletes an asset by its unique ID."""
        pass


class JobRepository(ABC):
    """Abstract interface for background job data operations."""

    @abstractmethod
    async def save(self, job: Job) -> Job:
        """Saves a job (and its steps)."""
        pass

    @abstractmethod
    async def get_by_id(self, job_id: str) -> Job | None:
        """Retrieves a job by its unique ID."""
        pass

    @abstractmethod
    async def list_by_project(self, project_id: str) -> list[Job]:
        """Lists all jobs associated with a specific project."""
        pass

    @abstractmethod
    async def delete(self, job_id: str) -> bool:
        """Deletes a job by its unique ID."""
        pass


class PresetRepository(ABC):
    """Abstract interface for preset data operations."""

    @abstractmethod
    async def save(self, preset: Preset) -> Preset:
        """Saves a preset."""
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> Preset | None:
        """Retrieves a preset by its unique name."""
        pass

    @abstractmethod
    async def list_by_category(self, category: str) -> list[Preset]:
        """Lists all presets in a specific module category."""
        pass

    @abstractmethod
    async def delete(self, preset_id: str) -> bool:
        """Deletes a preset by its unique ID."""
        pass
