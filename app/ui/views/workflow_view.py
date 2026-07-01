import uuid
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QPointF, QRectF, Qt, Slot
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from loguru import logger
from app.core.entities.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.ui.viewmodels.workflow_viewmodel import WorkflowViewModel


class NodeGraphicsItem(QGraphicsItem):
    """Visual representation of a workflow node on the canvas."""

    def __init__(self, node: WorkflowNode) -> None:
        super().__init__()
        self.node = node
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setPos(node.x, node.y)

        self.width = 160
        self.height = 100
        
        # Color based on node type
        type_colors = {
            "download": QColor("#059669"),      # Emerald
            "transcribe": QColor("#7C3AED"),    # Violet
            "translate": QColor("#2563EB"),     # Royal Blue
            "tts": QColor("#DB2777"),           # Pink
            "enhance": QColor("#D97706"),       # Amber
            "export": QColor("#4B5563"),        # Slate Gray
        }
        self.header_color = type_colors.get(node.node_type, QColor("#374151"))

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option: Any, widget: Optional[QWidget] = None) -> None:
        # Base background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#1F2937"))) # dark background
        painter.drawRoundedRect(self.boundingRect(), 8, 8)

        # Header area
        header_path = QPainterPath()
        header_path.addRoundedRect(QRectF(0, 0, self.width, 28), 8, 8)
        # Clip bottom corner rounding
        painter.setClipPath(header_path)
        painter.setBrush(QBrush(self.header_color))
        painter.drawRect(0, 0, self.width, 28)
        
        # Reset clipping
        painter.setClipping(False)

        # Text Header
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRectF(8, 0, self.width - 16, 28), Qt.AlignmentFlag.AlignVCenter, self.node.title)

        # Border outline (Highlighted when selected)
        if self.isSelected():
            painter.setPen(QPen(QColor("#3B82F6"), 2))
        else:
            painter.setPen(QPen(QColor("#374151"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.boundingRect(), 8, 8)

        # Status text or progress bar if executing
        if self.node.status != "IDLE":
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(QRectF(8, 70, self.width - 16, 24), Qt.AlignmentFlag.AlignVCenter, f"{self.node.status} ({self.node.progress:.0f}%)")

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            self.node.x = new_pos.x()
            self.node.y = new_pos.y()
            # Request connection lines update
            self.scene().update()
        return super().itemChange(change, value)


class ConnectionGraphicsItem(QGraphicsPathItem):
    """Visual Bezier curve connecting output ports to input ports."""

    def __init__(self, source_item: NodeGraphicsItem, target_item: NodeGraphicsItem) -> None:
        super().__init__()
        self.source = source_item
        self.target = target_item
        
        self.setPen(QPen(QColor("#94A3B8"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        self.update_path()

    def update_path(self) -> None:
        # Calculate port anchor points (source right center, target left center)
        p_src = self.source.pos() + QPointF(self.source.width, 50)
        p_tgt = self.target.pos() + QPointF(0, 50)

        path = QPainterPath()
        path.moveTo(p_src)
        
        # Draw dynamic cubic bezier curve
        dx = abs(p_tgt.x() - p_src.x()) * 0.5
        ctrl1 = p_src + QPointF(dx, 0)
        ctrl2 = p_tgt - QPointF(dx, 0)
        path.cubicTo(ctrl1, ctrl2, p_tgt)
        
        self.setPath(path)


class WorkflowCanvasView(QGraphicsView):
    """Interactive canvas supporting nodes navigation and connection links drawing."""

    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setStyleSheet("QGraphicsView { background-color: #0B0C0E; border: none; }")


class WorkflowView(QFrame):
    """Main Workflow layout coordinating visual canvas, nodes sidebar and execute controls."""

    def __init__(self, viewmodel: WorkflowViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self._vm = viewmodel
        
        # Initialize default empty workflow entity
        self._workflow = Workflow(id="default", name="Chained Media Dubbing")
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

        # Setup toolbar
        self._setup_toolbar()

        # Splitter to divide visual canvas and property editor panel
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._layout.addWidget(self._splitter, stretch=1)

        # Setup Canvas Scene
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(0, 0, 2000, 2000)
        
        self._canvas = WorkflowCanvasView(self._scene)
        self._splitter.addWidget(self._canvas)

        # Setup Properties sidebar panel
        self._setup_sidebar()

        # Connect scene selection change trigger to update properties
        self._scene.selectionChanged.connect(self._on_selection_changed)

        # Connect viewmodel slots
        self._vm.node_status_changed.connect(self._on_node_status_changed)
        self._vm.node_progress_updated.connect(self._on_node_progress_updated)
        self._vm.workflow_progress.connect(self._on_workflow_progress)
        self._vm.workflow_completed.connect(self._on_workflow_completed)
        self._vm.workflow_failed.connect(self._on_workflow_failed)

        # Load a default visual workflow template immediately
        self._load_default_template()

    def _setup_toolbar(self) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._run_btn = QPushButton("Run Workflow (DAG)")
        self._run_btn.setObjectName("primaryButton")
        self._run_btn.clicked.connect(self._on_run_clicked)
        layout.addWidget(self._run_btn)

        self._add_node_combo = QComboBox()
        self._add_node_combo.addItems([
            "-- Add Action Node --",
            "Download Video",
            "Transcribe Audio",
            "Translate Subtitles",
            "TTS Dubbing",
            "Enhance Quality",
        ])
        self._add_node_combo.currentIndexChanged.connect(self._on_add_node_selected)
        layout.addWidget(self._add_node_combo)

        self._clear_btn = QPushButton("Clear Canvas")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        layout.addWidget(self._clear_btn)

        # Dynamic overall execution progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self._status_label)

        self._layout.addWidget(container)

    def _setup_sidebar(self) -> None:
        self._sidebar = QFrame()
        self._sidebar.setFrameShape(QFrame.Shape.StyledPanel)
        self._sidebar.setStyleSheet("QFrame { background-color: #16181C; border-radius: 6px; }")
        self._sidebar_layout = QVBoxLayout(self._sidebar)
        self._sidebar_layout.setContentsMargins(16, 16, 16, 16)
        self._sidebar_layout.setSpacing(12)

        title = QLabel("Properties Panel")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        self._sidebar_layout.addWidget(title)

        self._prop_label = QLabel("Select a node on the canvas to configure properties.")
        self._prop_label.setWordWrap(True)
        self._prop_label.setStyleSheet("color: #94A3B8;")
        self._sidebar_layout.addWidget(self._prop_label)

        # Reusable settings fields
        self._prop_input_1_lbl = QLabel("")
        self._prop_input_1 = QLineEdit()
        self._prop_input_1.textChanged.connect(self._on_prop_changed)
        self._sidebar_layout.addWidget(self._prop_input_1_lbl)
        self._sidebar_layout.addWidget(self._prop_input_1)

        self._prop_input_2_lbl = QLabel("")
        self._prop_input_2 = QLineEdit()
        self._prop_input_2.textChanged.connect(self._on_prop_changed)
        self._sidebar_layout.addWidget(self._prop_input_2_lbl)
        self._sidebar_layout.addWidget(self._prop_input_2)

        self._prop_input_1_lbl.setVisible(False)
        self._prop_input_1.setVisible(False)
        self._prop_input_2_lbl.setVisible(False)
        self._prop_input_2.setVisible(False)

        self._sidebar_layout.addStretch()
        self._splitter.addWidget(self._sidebar)
        
        # Balance initial splitter distribution
        self._splitter.setSizes([800, 250])

    def _on_selection_changed(self) -> None:
        selected = self._scene.selectedItems()
        if not selected or not isinstance(selected[0], NodeGraphicsItem):
            # Hide property fields
            self._prop_label.setText("Select a node on the canvas to configure properties.")
            self._prop_label.setVisible(True)
            self._prop_input_1_lbl.setVisible(False)
            self._prop_input_1.setVisible(False)
            self._prop_input_2_lbl.setVisible(False)
            self._prop_input_2.setVisible(False)
            return

        item = selected[0]
        node = item.node
        self._prop_label.setVisible(False)

        # Contextual properties update
        self._prop_input_1_lbl.setVisible(True)
        self._prop_input_1.setVisible(True)
        self._prop_input_1.blockSignals(True)

        if node.node_type == "download":
            self._prop_input_1_lbl.setText("Download URL:")
            self._prop_input_1.setText(node.properties.get("url", ""))
            self._prop_input_2_lbl.setVisible(False)
            self._prop_input_2.setVisible(False)
            
        elif node.node_type == "transcribe":
            self._prop_input_1_lbl.setText("Provider (whisper/openai):")
            self._prop_input_1.setText(node.properties.get("provider", "whisper"))
            self._prop_input_2_lbl.setVisible(False)
            self._prop_input_2.setVisible(False)

        elif node.node_type == "translate":
            self._prop_input_1_lbl.setText("Target Language:")
            self._prop_input_1.setText(node.properties.get("target_lang", "vi"))
            self._prop_input_2_lbl.setVisible(False)
            self._prop_input_2.setVisible(False)

        elif node.node_type == "tts":
            self._prop_input_1_lbl.setText("Voice ID:")
            self._prop_input_1.setText(node.properties.get("voice_id", "alloy"))
            self._prop_input_2_lbl.setVisible(False)
            self._prop_input_2.setVisible(False)

        elif node.node_type == "enhance":
            self._prop_input_1_lbl.setText("Task Type (upscale/denoise):")
            self._prop_input_1.setText(node.properties.get("task_type", "upscale"))
            self._prop_input_2_lbl.setVisible(False)
            self._prop_input_2.setVisible(False)

        elif node.node_type == "export":
            self._prop_input_1_lbl.setText("Destination Path:")
            self._prop_input_1.setText(node.properties.get("destination_path", ""))
            self._prop_input_2_lbl.setVisible(False)
            self._prop_input_2.setVisible(False)

        self._prop_input_1.blockSignals(False)

    def _on_prop_changed(self) -> None:
        selected = self._scene.selectedItems()
        if not selected or not isinstance(selected[0], NodeGraphicsItem):
            return
        
        node = selected[0].node
        val1 = self._prop_input_1.text().strip()

        if node.node_type == "download":
            node.properties["url"] = val1
        elif node.node_type == "transcribe":
            node.properties["provider"] = val1
        elif node.node_type == "translate":
            node.properties["target_lang"] = val1
        elif node.node_type == "tts":
            node.properties["voice_id"] = val1
        elif node.node_type == "enhance":
            node.properties["task_type"] = val1
        elif node.node_type == "export":
            node.properties["destination_path"] = val1

    def _on_add_node_selected(self, index: int) -> None:
        if index == 0:
            return

        types = ["", "download", "transcribe", "translate", "tts", "enhance"]
        node_type = types[index]
        titles = ["", "Download Video", "Transcribe Audio", "Translate Subtitles", "TTS Dubbing", "Enhance Quality"]
        title = titles[index]

        nid = f"{node_type}_{str(uuid.uuid4())[:6]}"
        node = WorkflowNode(id=nid, node_type=node_type, title=title, x=100, y=100)
        self._workflow.nodes.append(node)

        # Add to canvas scene
        item = NodeGraphicsItem(node)
        self._scene.addItem(item)
        
        # Reset dropdown index
        self._add_node_combo.setCurrentIndex(0)

    def _on_clear_clicked(self) -> None:
        self._scene.clear()
        self._workflow.nodes.clear()
        self._workflow.edges.clear()

    def _load_default_template(self) -> None:
        """Loads a clean pre-built workflow chain on canvas init."""
        self._on_clear_clicked()

        # Nodes creation
        node_dl = WorkflowNode(
            id="node_dl",
            node_type="download",
            title="Download Video",
            properties={"url": "https://youtube.com/watch?v=123", "quality": "highest"},
            x=50.0,
            y=150.0,
        )
        node_stt = WorkflowNode(
            id="node_stt",
            node_type="transcribe",
            title="Transcribe Audio",
            properties={"provider": "whisper", "mock": True},
            x=280.0,
            y=150.0,
        )
        node_trans = WorkflowNode(
            id="node_trans",
            node_type="translate",
            title="Translate Subtitles",
            properties={"provider": "google", "target_lang": "vi", "mock": True},
            x=510.0,
            y=150.0,
        )
        node_tts = WorkflowNode(
            id="node_tts",
            node_type="tts",
            title="Voice Dubbing",
            properties={"provider": "local", "voice_id": "alloy", "mock": True},
            x=740.0,
            y=150.0,
        )

        self._workflow.nodes.extend([node_dl, node_stt, node_trans, node_tts])

        # Edge Connections creation
        # Download output file_path -> Transcribe input file_path
        edge1 = WorkflowEdge("e1", "node_dl", "file_path", "node_stt", "file_path")
        # Transcribe output subtitles_path -> Translate input subtitles_path
        edge2 = WorkflowEdge("e2", "node_stt", "subtitles_path", "node_trans", "subtitles_path")
        # Translate output subtitles_path -> TTS input subtitles_path
        edge3 = WorkflowEdge("e3", "node_trans", "subtitles_path", "node_tts", "subtitles_path")

        self._workflow.edges.extend([edge1, edge2, edge3])

        # Draw on canvas scene
        node_items = {}
        for node in self._workflow.nodes:
            item = NodeGraphicsItem(node)
            self._scene.addItem(item)
            node_items[node.id] = item

        for edge in self._workflow.edges:
            src_item = node_items[edge.source_node_id]
            tgt_item = node_items[edge.target_node_id]
            connection = ConnectionGraphicsItem(src_item, tgt_item)
            self._scene.addItem(connection)

    def _on_run_clicked(self) -> None:
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Initializing DAG Engine...")
        self._run_btn.setEnabled(False)

        # Start execution
        self._vm.run_workflow("default", self._workflow)

    # Viewmodel Callbacks Slots
    @Slot(str, float)
    def _on_workflow_progress(self, job_id: str, percent: float) -> None:
        self._progress_bar.setValue(int(percent))
        self._status_label.setText(f"Workflow Executing: {percent:.1f}%")

    @Slot(str, str, str)
    def _on_node_status_changed(self, job_id: str, node_id: str, status: str) -> None:
        # Search node graphics item to trigger repaint with new status color / label
        for item in self._scene.items():
            if isinstance(item, NodeGraphicsItem) and item.node.id == node_id:
                item.node.status = status
                if status == "COMPLETED":
                    item.node.progress = 100.0
                item.update()
                break

    @Slot(str, str, float)
    def _on_node_progress_updated(self, job_id: str, node_id: str, percent: float) -> None:
        for item in self._scene.items():
            if isinstance(item, NodeGraphicsItem) and item.node.id == node_id:
                item.node.progress = percent
                item.update()
                break

    @Slot(str, dict)
    def _on_workflow_completed(self, job_id: str, results: dict[str, Any]) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Completed Successfully")
        self._status_label.setStyleSheet("color: #10B981; font-size: 12px;")
        self._run_btn.setEnabled(True)

    @Slot(str, str)
    def _on_workflow_failed(self, job_id: str, error_msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Failed")
        self._status_label.setStyleSheet("color: #EF4444; font-size: 12px;")
        self._run_btn.setEnabled(True)
        logger.error("Workflow job failed: {}", error_msg)


from typing import Optional
