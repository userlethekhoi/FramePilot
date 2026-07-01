from dataclasses import dataclass


@dataclass
class Preset:
    name: str
    category: str  # downloader, enhancer, subtitle, etc.
    payload_json: str
    id: str | None = None
