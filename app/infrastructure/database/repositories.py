from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.entities.asset import Asset
from app.core.entities.job import Job, JobStep
from app.core.entities.preset import Preset
from app.core.entities.project import Project
from app.core.interfaces.repository import (
    AssetRepository,
    JobRepository,
    PresetRepository,
    ProjectRepository,
)
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.models import (
    AssetModel,
    JobModel,
    JobStepModel,
    PresetModel,
    ProjectModel,
)


class SqlAlchemyProjectRepository(ProjectRepository):
    """SQLAlchemy implementation of ProjectRepository."""

    def __init__(self, db_engine: DatabaseEngine) -> None:
        self._db = db_engine

    async def save(self, project: Project) -> Project:
        async with self._db.get_session() as session:
            if project.id:
                # Update existing
                result = await session.execute(
                    select(ProjectModel).where(ProjectModel.id == project.id)
                )
                model = result.scalar_one_or_none()
                if model:
                    model.name = project.name
                    model.path = project.path
                    model.settings_json = project.settings_json
                    await session.flush()
                    project.updated_at = model.updated_at
                    return project

            # Insert new
            model = ProjectModel(
                name=project.name,
                path=project.path,
                settings_json=project.settings_json,
            )
            if project.id:
                model.id = project.id

            session.add(model)
            await session.flush()

            project.id = model.id
            project.created_at = model.created_at
            project.updated_at = model.updated_at
            return project

    async def get_by_id(self, project_id: str) -> Project | None:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(ProjectModel).where(ProjectModel.id == project_id)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            return Project(
                id=model.id,
                name=model.name,
                path=model.path,
                created_at=model.created_at,
                updated_at=model.updated_at,
                settings_json=model.settings_json,
            )

    async def list_all(self) -> list[Project]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(ProjectModel).order_by(ProjectModel.updated_at.desc())
            )
            models = result.scalars().all()
            return [
                Project(
                    id=m.id,
                    name=m.name,
                    path=m.path,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                    settings_json=m.settings_json,
                )
                for m in models
            ]

    async def delete(self, project_id: str) -> bool:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(ProjectModel).where(ProjectModel.id == project_id)
            )
            model = result.scalar_one_or_none()
            if not model:
                return False
            await session.delete(model)
            return True


class SqlAlchemyAssetRepository(AssetRepository):
    """SQLAlchemy implementation of AssetRepository."""

    def __init__(self, db_engine: DatabaseEngine) -> None:
        self._db = db_engine

    async def save(self, asset: Asset) -> Asset:
        async with self._db.get_session() as session:
            if asset.id:
                result = await session.execute(select(AssetModel).where(AssetModel.id == asset.id))
                model = result.scalar_one_or_none()
                if model:
                    model.name = asset.name
                    model.file_path = asset.file_path
                    model.asset_type = asset.asset_type
                    model.metadata_json = asset.metadata_json
                    await session.flush()
                    return asset

            model = AssetModel(
                project_id=asset.project_id,
                name=asset.name,
                file_path=asset.file_path,
                asset_type=asset.asset_type,
                metadata_json=asset.metadata_json,
            )
            if asset.id:
                model.id = asset.id

            session.add(model)
            await session.flush()

            asset.id = model.id
            asset.imported_at = model.imported_at
            return asset

    async def get_by_id(self, asset_id: str) -> Asset | None:
        async with self._db.get_session() as session:
            result = await session.execute(select(AssetModel).where(AssetModel.id == asset_id))
            model = result.scalar_one_or_none()
            if not model:
                return None
            return Asset(
                id=model.id,
                project_id=model.project_id,
                name=model.name,
                file_path=model.file_path,
                asset_type=model.asset_type,
                metadata_json=model.metadata_json,
                imported_at=model.imported_at,
            )

    async def list_by_project(self, project_id: str) -> list[Asset]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(AssetModel)
                .where(AssetModel.project_id == project_id)
                .order_by(AssetModel.imported_at.desc())
            )
            models = result.scalars().all()
            return [
                Asset(
                    id=m.id,
                    project_id=m.project_id,
                    name=m.name,
                    file_path=m.file_path,
                    asset_type=m.asset_type,
                    metadata_json=m.metadata_json,
                    imported_at=m.imported_at,
                )
                for m in models
            ]

    async def delete(self, asset_id: str) -> bool:
        async with self._db.get_session() as session:
            result = await session.execute(select(AssetModel).where(AssetModel.id == asset_id))
            model = result.scalar_one_or_none()
            if not model:
                return False
            await session.delete(model)
            return True


class SqlAlchemyJobRepository(JobRepository):
    """SQLAlchemy implementation of JobRepository."""

    def __init__(self, db_engine: DatabaseEngine) -> None:
        self._db = db_engine

    async def save(self, job: Job) -> Job:
        async with self._db.get_session() as session:
            if job.id:
                result = await session.execute(
                    select(JobModel)
                    .options(selectinload(JobModel.steps))
                    .where(JobModel.id == job.id)
                )
                model = result.scalar_one_or_none()
                if model:
                    model.status = job.status
                    model.priority = job.priority
                    model.completed_at = job.completed_at

                    # Sync steps: For simplicity in desktop app, replace/update steps
                    # Delete existing steps first, then recreate or match ids.
                    # Given it's SQLite, simple recreation of modified steps or full sync:
                    await session.execute(delete(JobStepModel).where(JobStepModel.job_id == job.id))

                    for step in job.steps:
                        step_model = JobStepModel(
                            job_id=job.id,
                            step_type=step.step_type,
                            status=step.status,
                            progress=step.progress,
                            logs=step.logs,
                        )
                        if step.id:
                            step_model.id = step.id
                        session.add(step_model)

                    await session.flush()
                    return job

            model = JobModel(
                project_id=job.project_id,
                workflow_id=job.workflow_id,
                status=job.status,
                priority=job.priority,
                completed_at=job.completed_at,
            )
            if job.id:
                model.id = job.id

            session.add(model)
            await session.flush()

            job.id = model.id
            job.scheduled_at = model.scheduled_at

            for step in job.steps:
                step_model = JobStepModel(
                    job_id=model.id,
                    step_type=step.step_type,
                    status=step.status,
                    progress=step.progress,
                    logs=step.logs,
                )
                if step.id:
                    step_model.id = step.id
                session.add(step_model)
                await session.flush()
                step.id = step_model.id

            return job

    async def get_by_id(self, job_id: str) -> Job | None:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(JobModel).options(selectinload(JobModel.steps)).where(JobModel.id == job_id)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            steps = [
                JobStep(
                    id=sm.id,
                    step_type=sm.step_type,
                    status=sm.status,
                    progress=sm.progress,
                    logs=sm.logs,
                )
                for sm in model.steps
            ]

            return Job(
                id=model.id,
                project_id=model.project_id,
                workflow_id=model.workflow_id,
                status=model.status,
                priority=model.priority,
                scheduled_at=model.scheduled_at,
                completed_at=model.completed_at,
                steps=steps,
            )

    async def list_by_project(self, project_id: str) -> list[Job]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(JobModel)
                .options(selectinload(JobModel.steps))
                .where(JobModel.project_id == project_id)
                .order_by(JobModel.scheduled_at.desc())
            )
            models = result.scalars().all()

            jobs = []
            for m in models:
                steps = [
                    JobStep(
                        id=sm.id,
                        step_type=sm.step_type,
                        status=sm.status,
                        progress=sm.progress,
                        logs=sm.logs,
                    )
                    for sm in m.steps
                ]
                jobs.append(
                    Job(
                        id=m.id,
                        project_id=m.project_id,
                        workflow_id=m.workflow_id,
                        status=m.status,
                        priority=m.priority,
                        scheduled_at=m.scheduled_at,
                        completed_at=m.completed_at,
                        steps=steps,
                    )
                )
            return jobs

    async def delete(self, job_id: str) -> bool:
        async with self._db.get_session() as session:
            result = await session.execute(select(JobModel).where(JobModel.id == job_id))
            model = result.scalar_one_or_none()
            if not model:
                return False
            await session.delete(model)
            return True


class SqlAlchemyPresetRepository(PresetRepository):
    """SQLAlchemy implementation of PresetRepository."""

    def __init__(self, db_engine: DatabaseEngine) -> None:
        self._db = db_engine

    async def save(self, preset: Preset) -> Preset:
        async with self._db.get_session() as session:
            if preset.id:
                result = await session.execute(
                    select(PresetModel).where(PresetModel.id == preset.id)
                )
                model = result.scalar_one_or_none()
                if model:
                    model.name = preset.name
                    model.category = preset.category
                    model.payload_json = preset.payload_json
                    await session.flush()
                    return preset

            # Try by unique name constraint
            result = await session.execute(
                select(PresetModel).where(PresetModel.name == preset.name)
            )
            model = result.scalar_one_or_none()
            if model:
                model.category = preset.category
                model.payload_json = preset.payload_json
                await session.flush()
                preset.id = model.id
                return preset

            model = PresetModel(
                name=preset.name,
                category=preset.category,
                payload_json=preset.payload_json,
            )
            if preset.id:
                model.id = preset.id

            session.add(model)
            await session.flush()
            preset.id = model.id
            return preset

    async def get_by_name(self, name: str) -> Preset | None:
        async with self._db.get_session() as session:
            result = await session.execute(select(PresetModel).where(PresetModel.name == name))
            model = result.scalar_one_or_none()
            if not model:
                return None
            return Preset(
                id=model.id,
                name=model.name,
                category=model.category,
                payload_json=model.payload_json,
            )

    async def list_by_category(self, category: str) -> list[Preset]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(PresetModel)
                .where(PresetModel.category == category)
                .order_by(PresetModel.name.asc())
            )
            models = result.scalars().all()
            return [
                Preset(
                    id=m.id,
                    name=m.name,
                    category=m.category,
                    payload_json=m.payload_json,
                )
                for m in models
            ]

    async def delete(self, preset_id: str) -> bool:
        async with self._db.get_session() as session:
            result = await session.execute(select(PresetModel).where(PresetModel.id == preset_id))
            model = result.scalar_one_or_none()
            if not model:
                return False
            await session.delete(model)
            return True
