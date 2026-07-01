import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


def generate_uuid() -> str:
    """Helper to generate standard string UUIDs for primary keys."""
    return str(uuid.uuid4())


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    assets: Mapped[list["AssetModel"]] = relationship(
        "AssetModel", back_populates="project", cascade="all, delete-orphan"
    )
    workflows: Mapped[list["WorkflowModel"]] = relationship(
        "WorkflowModel", back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["JobModel"]] = relationship(
        "JobModel", back_populates="project", cascade="all, delete-orphan"
    )


class AssetModel(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    asset_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # video, audio, image, subtitle, etc.
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Relationships
    project: Mapped[ProjectModel] = relationship("ProjectModel", back_populates="assets")


class WorkflowModel(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dag_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    project: Mapped[ProjectModel] = relationship("ProjectModel", back_populates="workflows")
    jobs: Mapped[list["JobModel"]] = relationship("JobModel", back_populates="workflow")


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING"
    )  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    priority: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    project: Mapped[ProjectModel] = relationship("ProjectModel", back_populates="jobs")
    workflow: Mapped[WorkflowModel | None] = relationship("WorkflowModel", back_populates="jobs")
    steps: Mapped[list["JobStepModel"]] = relationship(
        "JobStepModel", back_populates="job", cascade="all, delete-orphan"
    )


class JobStepModel(Base):
    __tablename__ = "job_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    step_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING"
    )  # PENDING, RUNNING, COMPLETED, FAILED
    progress: Mapped[float] = mapped_column(Integer, default=0)  # 0 to 100
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    job: Mapped[JobModel] = relationship("JobModel", back_populates="steps")


class PresetModel(Base):
    __tablename__ = "presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # downloader, enhancer, subtitle, etc.
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
