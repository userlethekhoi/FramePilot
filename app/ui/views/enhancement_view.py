from typing import Any, Optional
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from loguru import logger
from app.ui.viewmodels.enhancement_viewmodel import EnhancementViewModel
from app.infrastructure.config.translation import tr


class EnhancementView(QFrame):
    """AI Media Quality Enhancement panel for upscaling, denoising, and framerate modifications."""

    def __init__(self, viewmodel: EnhancementViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self._vm = viewmodel
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(20)

        # Header Title
        self._title = QLabel(tr("enh.title"))
        self._title.setStyleSheet("font-size: 20px; font-weight: bold;")
        self._layout.addWidget(self._title)

        # 1. Media Source Picker
        self._setup_source_picker()

        # 2. Filter Selector & Contextual Settings Form
        self._setup_filters_form()

        # 3. Actions & Progress Bar
        self._setup_actions_section()

        # 4. Logs Output Display
        self._setup_logs_output()

        # Connect signals
        self._vm.enhancement_progress.connect(self._on_progress)
        self._vm.enhancement_completed.connect(self._on_completed)
        self._vm.enhancement_failed.connect(self._on_failed)

    def _setup_source_picker(self) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        file_label = QLabel(tr("enh.file_lbl"))
        layout.addWidget(file_label)

        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("Select input video or image file (.mp4, .png, .jpg)...")
        layout.addWidget(self._path_input, stretch=1)

        self._browse_btn = QPushButton("Browse")
        self._browse_btn.clicked.connect(self._on_browse_clicked)
        layout.addWidget(self._browse_btn)

        self._layout.addWidget(container)

    def _setup_filters_form(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Dropdown selection for the task type
        sel_container = QWidget()
        sel_layout = QHBoxLayout(sel_container)
        sel_layout.setContentsMargins(0, 0, 0, 0)
        
        filter_label = QLabel(tr("enh.type_lbl"))
        sel_layout.addWidget(filter_label)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            "Upscale (Double Resolution)",
            "Denoise (Remove Noise)",
            "Adjust FPS (Interpolation)",
            "Custom Resize (Resolution)",
        ])
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        sel_layout.addWidget(self._filter_combo)
        sel_layout.addStretch()
        layout.addWidget(sel_container)

        # Grid container for contextual parameters
        self._settings_grid = QFrame()
        self._settings_grid.setFrameShape(QFrame.Shape.StyledPanel)
        self._settings_grid.setStyleSheet("QFrame { background-color: rgba(255,255,255,0.03); border-radius: 8px; }")
        
        self._grid_layout = QGridLayout(self._settings_grid)
        self._grid_layout.setContentsMargins(16, 16, 16, 16)
        self._grid_layout.setSpacing(12)

        # Add parameters
        self._setup_parameters()
        layout.addWidget(self._settings_grid)
        
        self._layout.addWidget(container)

    def _setup_parameters(self) -> None:
        # Upscale options
        self._scale_lbl = QLabel("Scale Multiplier:")
        self._scale_combo = QComboBox()
        self._scale_combo.addItems(["2x", "4x"])
        self._grid_layout.addWidget(self._scale_lbl, 0, 0)
        self._grid_layout.addWidget(self._scale_combo, 0, 1)

        # Denoise options
        self._denoise_lbl = QLabel("Noise Reduction Level:")
        self._denoise_combo = QComboBox()
        self._denoise_combo.addItems(["low", "medium", "high"])
        self._denoise_combo.setCurrentText("medium")
        self._grid_layout.addWidget(self._denoise_lbl, 0, 0)
        self._grid_layout.addWidget(self._denoise_combo, 0, 1)

        # FPS options
        self._fps_lbl = QLabel("Target Frame Rate (FPS):")
        self._fps_input = QLineEdit()
        self._fps_input.setText("60")
        self._grid_layout.addWidget(self._fps_lbl, 0, 0)
        self._grid_layout.addWidget(self._fps_input, 0, 1)

        # Resize options
        self._w_lbl = QLabel("Width:")
        self._w_input = QLineEdit()
        self._w_input.setText("1920")
        self._h_lbl = QLabel("Height:")
        self._h_input = QLineEdit()
        self._h_input.setText("1080")
        
        self._grid_layout.addWidget(self._w_lbl, 0, 0)
        self._grid_layout.addWidget(self._w_input, 0, 1)
        self._grid_layout.addWidget(self._h_lbl, 1, 0)
        self._grid_layout.addWidget(self._h_input, 1, 1)

        # Initialize view state
        self._on_filter_changed(0)

    def _on_filter_changed(self, index: int) -> None:
        # Hide all first
        self._scale_lbl.setVisible(False)
        self._scale_combo.setVisible(False)
        self._denoise_lbl.setVisible(False)
        self._denoise_combo.setVisible(False)
        self._fps_lbl.setVisible(False)
        self._fps_input.setVisible(False)
        self._w_lbl.setVisible(False)
        self._w_input.setVisible(False)
        self._h_lbl.setVisible(False)
        self._h_input.setVisible(False)

        if index == 0:  # Upscale
            self._scale_lbl.setVisible(True)
            self._scale_combo.setVisible(True)
        elif index == 1:  # Denoise
            self._denoise_lbl.setVisible(True)
            self._denoise_combo.setVisible(True)
        elif index == 2:  # Adjust FPS
            self._fps_lbl.setVisible(True)
            self._fps_input.setVisible(True)
        elif index == 3:  # Resize
            self._w_lbl.setVisible(True)
            self._w_input.setVisible(True)
            self._h_lbl.setVisible(True)
            self._h_input.setVisible(True)

    def _setup_actions_section(self) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._enhance_btn = QPushButton(tr("enh.btn"))
        self._enhance_btn.setObjectName("primaryButton")
        self._enhance_btn.clicked.connect(self._on_enhance_clicked)
        layout.addWidget(self._enhance_btn)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self._status_label)

        self._layout.addWidget(container)

    def _setup_logs_output(self) -> None:
        out_label = QLabel("Enhancement Logs Output")
        out_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        self._layout.addWidget(out_label)

        self._logs_text = QPlainTextEdit()
        self._logs_text.setReadOnly(True)
        self._logs_text.setPlaceholderText("Logs and progress outputs from FFmpeg filter chains will display here...")
        self._logs_text.setStyleSheet(
            "QPlainTextEdit { font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }"
        )
        self._layout.addWidget(self._logs_text, stretch=1)

    def _on_browse_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video/Image source file",
            "",
            "Media Files (*.mp4 *.mkv *.png *.jpg *.jpeg *.avi *.mov *.webm);;All Files (*)",
        )
        if file_path:
            self._path_input.setText(file_path)

    def _on_enhance_clicked(self) -> None:
        path = self._path_input.text().strip()
        if not path:
            self._logs_text.setPlainText("Error: Please select a valid input file path.")
            return

        filter_idx = self._filter_combo.currentIndex()
        task_types = ["upscale", "denoise", "fps_adjust", "resize"]
        task_type = task_types[filter_idx]

        # Read settings from GUI fields
        options: dict[str, Any] = {
            "provider": "ffmpeg",
            "mock": True,  # Running in mock mode to prevent system blockings in UI
        }

        if task_type == "upscale":
            scale_text = self._scale_combo.currentText()
            options["scale_multiplier"] = int(scale_text.replace("x", ""))
        elif task_type == "denoise":
            options["denoise_strength"] = self._denoise_combo.currentText()
        elif task_type == "fps_adjust":
            try:
                options["target_fps"] = int(self._fps_input.text())
            except ValueError:
                options["target_fps"] = 60
        elif task_type == "resize":
            try:
                options["width"] = int(self._w_input.text())
                options["height"] = int(self._h_input.text())
            except ValueError:
                options["width"] = 1280
                options["height"] = 720

        # UI refresh
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Starting...")
        self._enhance_btn.setEnabled(False)
        self._logs_text.clear()

        # Submit task
        self._vm.start_enhancement("default", path, task_type, options)

    @Slot(str, float)
    def _on_progress(self, job_id: str, percent: float) -> None:
        self._progress_bar.setValue(int(percent))
        self._status_label.setText(f"Processing: {percent:.1f}%")

    @Slot(str, str)
    def _on_completed(self, job_id: str, output_path: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Completed")
        self._status_label.setStyleSheet("color: #10B981; font-size: 12px;")
        self._enhance_btn.setEnabled(True)

        log = (
            f"=== Media Enhancement Completed ===\n"
            f"Enhanced file exported successfully to:\n"
            f"{output_path}"
        )
        self._logs_text.setPlainText(log)

    @Slot(str, str)
    def _on_failed(self, job_id: str, error_msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Failed")
        self._status_label.setStyleSheet("color: #EF4444; font-size: 12px;")
        self._enhance_btn.setEnabled(True)
        self._logs_text.setPlainText(f"Error: Enhancement filters failed.\nReason: {error_msg}")
