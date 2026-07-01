from dataclasses import dataclass


@dataclass
class Workflow:
    project_id: str
    name: str
    dag_json: str
    is_template: bool = False
    id: str | None = None
