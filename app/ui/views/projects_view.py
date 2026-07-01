from typing import Optional
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from app.ui.viewmodels.projects_viewmodel import ProjectsViewModel


class ProjectsView(QFrame):
    """Dashboard view for creating and selecting active project workspaces."""

    def __init__(self, viewmodel: ProjectsViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self._vm = viewmodel

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(20)

        # Welcome Title
        self._title = QLabel("Welcome to FramePilot")
        self._title.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFFFFF;")
        self._layout.addWidget(self._title)

        # Active Workspace Status Banner
        self._status_banner = QFrame()
        self._status_banner.setFrameShape(QFrame.Shape.StyledPanel)
        self._status_banner.setStyleSheet(
            "QFrame { background-color: rgba(16, 185, 129, 0.1); border: 1px solid #10B981; border-radius: 6px; }"
        )
        status_layout = QHBoxLayout(self._status_banner)
        status_layout.setContentsMargins(12, 12, 12, 12)
        
        self._status_lbl = QLabel(f"Active Workspace: {self._vm.active_project_name}")
        self._status_lbl.setStyleSheet("color: #10B981; font-weight: bold; font-size: 13px;")
        status_layout.addWidget(self._status_lbl)
        self._layout.addWidget(self._status_banner)

        # Splitter Layout (Create on Left, Select on Right)
        body_container = QWidget()
        body_layout = QHBoxLayout(body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(24)

        # Left Column: Create Project Form
        create_frame = QFrame()
        create_frame.setStyleSheet("QFrame { background-color: rgba(255,255,255,0.02); border-radius: 8px; }")
        create_layout = QVBoxLayout(create_frame)
        create_layout.setContentsMargins(16, 16, 16, 16)
        create_layout.setSpacing(12)

        create_title = QLabel("Create New Project")
        create_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        create_layout.addWidget(create_title)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("My awesome project...")
        form_layout.addRow("Project Name:", self._name_input)

        path_container = QWidget()
        path_layout = QHBoxLayout(path_container)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)

        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("C:/Users/...")
        path_layout.addWidget(self._path_input, stretch=1)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._on_browse_clicked)
        path_layout.addWidget(browse_btn)

        form_layout.addRow("Project Path:", path_container)
        create_layout.addWidget(form_widget)

        self._create_btn = QPushButton("Create Workspace")
        self._create_btn.setObjectName("primaryButton")
        self._create_btn.clicked.connect(self._on_create_clicked)
        create_layout.addWidget(self._create_btn)
        create_layout.addStretch()

        body_layout.addWidget(create_frame, stretch=1)

        # Right Column: Recent / Available Workspaces
        recent_frame = QFrame()
        recent_frame.setStyleSheet("QFrame { background-color: rgba(255,255,255,0.02); border-radius: 8px; }")
        recent_layout = QVBoxLayout(recent_frame)
        recent_layout.setContentsMargins(16, 16, 16, 16)
        recent_layout.setSpacing(12)

        recent_title = QLabel("Select Existing Workspace")
        recent_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        recent_layout.addWidget(recent_title)

        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet(
            "QListWidget { background-color: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); border-radius: 4px; }"
        )
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        recent_layout.addWidget(self._list_widget, stretch=1)

        self._select_btn = QPushButton("Load Workspace")
        self._select_btn.clicked.connect(self._on_load_clicked)
        recent_layout.addWidget(self._select_btn)

        body_layout.addWidget(recent_frame, stretch=1)
        self._layout.addWidget(body_container, stretch=1)

        # Connect signals
        self._vm.projects_updated.connect(self._refresh_list)
        self._vm.active_project_changed.connect(self._on_active_changed)

        # Initial loading
        self._vm.load_projects()

    def _on_browse_clicked(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder", "")
        if path:
            self._path_input.setText(path)

    def _on_create_clicked(self) -> None:
        name = self._name_input.text().strip()
        path = self._path_input.text().strip()
        if name and path:
            self._vm.create_project(name, path)
            self._name_input.clear()
            self._path_input.clear()

    def _on_load_clicked(self) -> None:
        curr_row = self._list_widget.currentRow()
        if curr_row >= 0:
            self._vm.select_project_index(curr_row)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        curr_row = self._list_widget.currentRow()
        if curr_row >= 0:
            self._vm.select_project_index(curr_row)

    @Slot()
    def _refresh_list(self) -> None:
        self._list_widget.clear()
        for p in self._vm.projects_list:
            self._list_widget.addItem(f"{p.name} [{p.path}]")

    @Slot(str)
    def _on_active_changed(self, name: str) -> None:
        self._status_lbl.setText(f"Active Workspace: {name}")
