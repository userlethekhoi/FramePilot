from dataclasses import dataclass
from datetime import datetime


@dataclass
class Asset:
    project_id: str
    name: str
    file_path: str
    asset_type: str  # video, audio, image, subtitle, etc.
    id: str | None = None
    metadata_json: str | None = None
    imported_at: datetime | None = None
