from typing import Any, Optional

from loguru import logger
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.viewmodels.downloader_viewmodel import DownloaderViewModel
from app.infrastructure.config.translation import tr


class ActiveDownloadRow(QFrame):
    """Custom row widget representing a running download job inside the active queue list."""

    def __init__(self, job_id: str, url: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self.setStyleSheet(
            "QFrame#panelFrame { padding: 12px; background-color: rgba(255, 255, 255, 0.02); }"
        )

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(6)

        # Info header
        self._header_layout = QHBoxLayout()
        self._title_label = QLabel(url)
        self._title_label.setStyleSheet("font-weight: bold;")
        self._title_label.setWordWrap(False)
        self._header_layout.addWidget(self._title_label)

        self._metrics_label = QLabel("Extracting metadata...")
        self._metrics_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self._metrics_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._header_layout.addWidget(self._metrics_label)
        self._layout.addLayout(self._header_layout)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._layout.addWidget(self._progress_bar)

    def update_progress(self, percentage: float, speed: float, eta: float) -> None:
        """Updates the progress bar values and status labels."""
        self._progress_bar.setValue(int(percentage))

        # Convert speed to KB/s or MB/s
        speed_kb = speed / 1024.0
        speed_str = f"{speed_kb / 1024.0:.2f} MB/s" if speed_kb > 1024.0 else f"{speed_kb:.1f} KB/s"

        # Convert ETA to minutes/seconds
        eta_str = f"{int(eta // 60)}m {int(eta % 60)}s" if eta > 60 else f"{int(eta)}s"

        self._metrics_label.setText(f"{percentage:.1f}% | Speed: {speed_str} | ETA: {eta_str}")

    def set_failed(self, error_msg: str) -> None:
        self._metrics_label.setText(f"Failed: {error_msg}")
        self._metrics_label.setStyleSheet("color: #EF4444; font-size: 11px;")

    def set_completed(self) -> None:
        self._progress_bar.setValue(100)
        self._metrics_label.setText("Completed")
        self._metrics_label.setStyleSheet("color: #10B981; font-size: 11px;")


class DownloaderView(QFrame):
    """Visual Downloader layout with input forms, quality selections, and active queues lists."""

    def __init__(self, viewmodel: DownloaderViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self._vm = viewmodel

        # Mapping active job layouts
        self._active_rows: dict[str, ActiveDownloadRow] = {}

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(20)

        # Header Title
        self._title = QLabel(tr("dl.title"))
        self._title.setStyleSheet("font-size: 20px; font-weight: bold;")
        self._layout.addWidget(self._title)

        # 1. URL Input Section
        self._setup_input_form()

        # 2. Options Grid Section
        self._setup_options_form()

        # 3. Active Queue Section
        self._setup_queue_view()

        # Bind View Model signals
        self._vm.download_progress.connect(self._on_download_progress)
        self._vm.download_completed.connect(self._on_download_completed)
        self._vm.download_failed.connect(self._on_download_failed)

    def _setup_input_form(self) -> None:
        """Sets up the URL text box and download buttons layout."""
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(12)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(tr("dl.url_lbl"))
        input_layout.addWidget(self._url_input, stretch=1)

        self._download_btn = QPushButton(tr("dl.start_btn"))
        self._download_btn.setObjectName("primaryButton")
        self._download_btn.clicked.connect(self._on_download_btn_clicked)
        input_layout.addWidget(self._download_btn)

        self._layout.addWidget(input_container)

    def _setup_options_form(self) -> None:
        """Sets up quality, format, and resolution dropdown settings."""
        options_container = QWidget()
        options_layout = QHBoxLayout(options_container)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(16)

        # Format choice dropdown
        format_label = QLabel(tr("dl.format_lbl"))
        options_layout.addWidget(format_label)

        self._format_combo = QComboBox()
        self._format_combo.addItems(
            [
                "Highest Quality (Best Video + Best Audio)",
                "Audio Only (MP3 format)",
                "Custom Resolution (Max 1080p)",
                "Custom Resolution (Max 720p)",
            ]
        )
        options_layout.addWidget(self._format_combo, stretch=1)

        options_layout.addStretch()
        self._layout.addWidget(options_container)

    def _setup_queue_view(self) -> None:
        """Sets up the scroll panel to list running downloads."""
        queue_label = QLabel(tr("dl.queue_lbl"))
        queue_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        self._layout.addWidget(queue_label)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._queue_widget = QWidget()
        self._queue_widget.setStyleSheet("background: transparent;")
        self._queue_layout = QVBoxLayout(self._queue_widget)
        self._queue_layout.setContentsMargins(0, 0, 0, 0)
        self._queue_layout.setSpacing(8)
        self._queue_layout.addStretch()  # Keep items pushed to top

        self._scroll_area.setWidget(self._queue_widget)
        self._layout.addWidget(self._scroll_area, stretch=1)

    def _on_download_btn_clicked(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            return

        # Resolve options based on combo index selection
        preset_idx = self._format_combo.currentIndex()
        options: dict[str, Any] = {}

        if preset_idx == 1:
            options["quality"] = "audio_only"
            options["audio_codec"] = "mp3"
        elif preset_idx == 2:
            options["quality"] = "custom_res"
            options["resolution"] = "1080"
        elif preset_idx == 3:
            options["quality"] = "custom_res"
            options["resolution"] = "720"
        else:
            options["quality"] = "highest"

        # Submit download job (using a dummy project ID "default" for standalone downloads)
        job_id = self._vm.trigger_download("default", url, options)

        # Add a progress row in the UI
        row = ActiveDownloadRow(job_id, url)
        # Add to top of scroll list (insert before the stretch)
        self._queue_layout.insertWidget(self._queue_layout.count() - 1, row)
        self._active_rows[job_id] = row

        # Clear input field
        self._url_input.clear()

    @Slot(str, float, float, float)
    def _on_download_progress(
        self, job_id: str, percentage: float, speed: float, eta: float
    ) -> None:
        row = self._active_rows.get(job_id)
        if row:
            row.update_progress(percentage, speed, eta)

    @Slot(str, str)
    def _on_download_completed(self, job_id: str, file_path: str) -> None:
        logger.info("Download completed in UI: {} -> {}", job_id, file_path)
        row = self._active_rows.get(job_id)
        if row:
            row.set_completed()

    @Slot(str, str)
    def _on_download_failed(self, job_id: str, error_msg: str) -> None:
        logger.error("Download failed in UI: {} -> {}", job_id, error_msg)
        row = self._active_rows.get(job_id)
        if row:
            row.set_failed(error_msg)


