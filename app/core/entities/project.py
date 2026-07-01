from dataclasses import dataclass
from datetime import datetime


@dataclass
class Project:
    name: str
    path: str
    id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    settings_json: str | None = None
