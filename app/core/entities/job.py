from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobStep:
    step_type: str
    id: str | None = None
    status: str = "PENDING"
    progress: float = 0.0
    logs: str | None = None


@dataclass
class Job:
    project_id: str
    id: str | None = None
    workflow_id: str | None = None
    status: str = "PENDING"
    priority: int = 0
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    steps: list[JobStep] = field(default_factory=list)
