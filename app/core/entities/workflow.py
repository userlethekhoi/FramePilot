from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WorkflowNode:
    """Represents an atomic task block (Node) within a MediaFlow AI workflow graph."""
    id: str
    node_type: str  # "download", "transcribe", "translate", "tts", "enhance", "export"
    title: str
    properties: Dict[str, Any] = field(default_factory=dict)
    
    # Visual coordinates on the editor canvas
    x: float = 0.0
    y: float = 0.0
    
    # Dynamic runtime state
    status: str = "IDLE"  # "IDLE", "RUNNING", "COMPLETED", "FAILED"
    progress: float = 0.0


@dataclass
class WorkflowEdge:
    """Represents a directional data connection between two workflow nodes."""
    id: str
    source_node_id: str
    source_port: str  # Output port name (e.g. "file_path", "subtitles_path")
    target_node_id: str
    target_port: str  # Input port name (e.g. "media_path", "text_path")


@dataclass
class Workflow:
    """Represents the Directed Acyclic Graph (DAG) configuration holding nodes and connections."""
    id: str
    name: str
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    
    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
