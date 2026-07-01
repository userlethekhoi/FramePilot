import pytest

from app.core.entities.asset import Asset
from app.core.entities.job import Job, JobStep
from app.core.entities.preset import Preset
from app.core.entities.project import Project
from app.infrastructure.database.connection import DatabaseEngine
from app.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyPresetRepository,
    SqlAlchemyProjectRepository,
)


@pytest.mark.asyncio
async def test_project_repository(db_engine: DatabaseEngine) -> None:
    repo = SqlAlchemyProjectRepository(db_engine)

    # 1. Create Project
    project = Project(name="Test Project", path="/path/to/project")
    saved_project = await repo.save(project)

    assert saved_project.id is not None
    assert saved_project.name == "Test Project"
    assert saved_project.created_at is not None

    # 2. Get Project by ID
    retrieved = await repo.get_by_id(saved_project.id)
    assert retrieved is not None
    assert retrieved.name == "Test Project"

    # 3. Update Project
    retrieved.name = "Updated Project Name"
    updated = await repo.save(retrieved)
    assert updated.name == "Updated Project Name"

    # 4. List Projects
    projects = await repo.list_all()
    assert len(projects) == 1
    assert projects[0].name == "Updated Project Name"

    # 5. Delete Project
    deleted = await repo.delete(saved_project.id)
    assert deleted is True

    retrieved_after_delete = await repo.get_by_id(saved_project.id)
    assert retrieved_after_delete is None


@pytest.mark.asyncio
async def test_asset_repository(db_engine: DatabaseEngine) -> None:
    proj_repo = SqlAlchemyProjectRepository(db_engine)
    asset_repo = SqlAlchemyAssetRepository(db_engine)

    # Create dummy project
    project = await proj_repo.save(Project(name="Proj", path="/p"))
    assert project.id is not None

    # 1. Save Asset
    asset = Asset(
        project_id=project.id,
        name="video1.mp4",
        file_path="/p/video1.mp4",
        asset_type="video",
        metadata_json='{"duration": 120}',
    )
    saved_asset = await asset_repo.save(asset)
    assert saved_asset.id is not None
    assert saved_asset.imported_at is not None

    # 2. List Assets by Project
    assets = await asset_repo.list_by_project(project.id)
    assert len(assets) == 1
    assert assets[0].name == "video1.mp4"

    # 3. Get Asset by ID
    retrieved = await asset_repo.get_by_id(saved_asset.id)
    assert retrieved is not None
    assert retrieved.name == "video1.mp4"

    # 4. Delete Asset
    deleted = await asset_repo.delete(saved_asset.id)
    assert deleted is True

    retrieved_after_delete = await asset_repo.get_by_id(saved_asset.id)
    assert retrieved_after_delete is None


@pytest.mark.asyncio
async def test_job_repository(db_engine: DatabaseEngine) -> None:
    proj_repo = SqlAlchemyProjectRepository(db_engine)
    job_repo = SqlAlchemyJobRepository(db_engine)

    # Create dummy project
    project = await proj_repo.save(Project(name="Proj", path="/p"))
    assert project.id is not None

    # 1. Save Job with Steps
    step1 = JobStep(step_type="download", status="COMPLETED", progress=100.0)
    step2 = JobStep(step_type="transcribe", status="RUNNING", progress=45.0)
    job = Job(
        project_id=project.id,
        status="RUNNING",
        priority=2,
        steps=[step1, step2],
    )

    saved_job = await job_repo.save(job)
    assert saved_job.id is not None
    assert len(saved_job.steps) == 2
    assert saved_job.steps[0].id is not None

    # 2. Get Job by ID
    retrieved = await job_repo.get_by_id(saved_job.id)
    assert retrieved is not None
    assert retrieved.status == "RUNNING"
    assert len(retrieved.steps) == 2
    assert retrieved.steps[1].step_type == "transcribe"
    assert retrieved.steps[1].progress == 45.0


@pytest.mark.asyncio
async def test_preset_repository(db_engine: DatabaseEngine) -> None:
    repo = SqlAlchemyPresetRepository(db_engine)

    # 1. Save Preset
    preset = Preset(name="TikTok HD", category="downloader", payload_json='{"res": "1080p"}')
    saved_preset = await repo.save(preset)
    assert saved_preset.id is not None

    # 2. Get Preset by Name
    retrieved = await repo.get_by_name("TikTok HD")
    assert retrieved is not None
    assert retrieved.category == "downloader"

    # 3. List by Category
    presets = await repo.list_by_category("downloader")
    assert len(presets) == 1
    assert presets[0].name == "TikTok HD"
