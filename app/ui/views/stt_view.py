from typing import Any, Dict
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
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
from app.ui.viewmodels.stt_viewmodel import SpeechToTextViewModel


class SpeechToTextView(QFrame):
    """Speech recognition GUI panel for audio transcriptions and subtitles exports."""

    def __init__(self, viewmodel: SpeechToTextViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self._vm = viewmodel
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(20)

        # Header Title
        self._title = QLabel("AI Speech Recognition (STT)")
        self._title.setStyleSheet("font-size: 20px; font-weight: bold;")
        self._layout.addWidget(self._title)

        # 1. File Picker Form
        self._setup_file_picker()

        # 2. Options Grid Section
        self._setup_options_form()

        # 3. Progress and Actions
        self._setup_progress_section()

        # 4. Transcribed Output Area
        self._setup_output_area()

        # Bind View Model signals
        self._vm.transcription_progress.connect(self._on_progress)
        self._vm.transcription_completed.connect(self._on_completed)
        self._vm.transcription_failed.connect(self._on_failed)

    def _setup_file_picker(self) -> None:
        """Sets up media file selector layout."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        file_label = QLabel("Media File:")
        layout.addWidget(file_label)

        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("Select video or audio file path (.wav, .mp3, .mp4, .mkv)...")
        layout.addWidget(self._path_input, stretch=1)

        self._browse_btn = QPushButton("Browse")
        self._browse_btn.clicked.connect(self._on_browse_clicked)
        layout.addWidget(self._browse_btn)

        self._layout.addWidget(container)

    def _setup_options_form(self) -> None:
        """Sets up STT provider, models, and languages settings dropdowns."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Provider Dropdown
        prov_label = QLabel("Provider:")
        layout.addWidget(prov_label)

        self._provider_combo = QComboBox()
        self._provider_combo.addItems([
            "Local Whisper (Offline)",
            "OpenAI Whisper (Cloud)",
        ])
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        layout.addWidget(self._provider_combo)

        # Model size dropdown
        self._model_label = QLabel("Model Size:")
        layout.addWidget(self._model_label)

        self._model_combo = QComboBox()
        self._model_combo.addItems(["tiny", "base", "small", "medium", "large"])
        self._model_combo.setCurrentText("base")
        layout.addWidget(self._model_combo)

        # Language input
        lang_label = QLabel("Language (Optional):")
        layout.addWidget(lang_label)
        
        self._lang_combo = QComboBox()
        self._lang_combo.addItems([
            "Auto-Detect",
            "en (English)",
            "vi (Vietnamese)",
            "zh (Chinese)",
            "ja (Japanese)",
            "fr (French)",
            "de (German)",
            "es (Spanish)",
        ])
        layout.addWidget(self._lang_combo)

        layout.addStretch()
        self._layout.addWidget(container)

    def _setup_progress_section(self) -> None:
        """Sets up trigger buttons and execution progress widgets."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._transcribe_btn = QPushButton("Start Transcription")
        self._transcribe_btn.setObjectName("primaryButton")
        self._transcribe_btn.clicked.connect(self._on_transcribe_clicked)
        layout.addWidget(self._transcribe_btn)

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

    def _setup_output_area(self) -> None:
        """Sets up the large text area displaying the transcription results."""
        out_label = QLabel("Transcription Output Log")
        out_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        self._layout.addWidget(out_label)

        self._output_text = QPlainTextEdit()
        self._output_text.setReadOnly(True)
        self._output_text.setPlaceholderText("Transcribed text and logs will appear here...")
        self._output_text.setStyleSheet(
            "QPlainTextEdit { font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }"
        )
        self._layout.addWidget(self._output_text, stretch=1)

    def _on_browse_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio/Video file",
            "",
            "Media Files (*.mp3 *.wav *.mp4 *.mkv *.avi *.mov);;All Files (*)",
        )
        if file_path:
            self._path_input.setText(file_path)

    def _on_provider_changed(self, index: int) -> None:
        # Hide model size dropdown for cloud OpenAI (which does not configure local model sizes)
        is_local = index == 0
        self._model_label.setVisible(is_local)
        self._model_combo.setVisible(is_local)

    def _on_transcribe_clicked(self) -> None:
        path = self._path_input.text().strip()
        if not path:
            self._output_text.setPlainText("Error: Please select a valid media file path.")
            return

        # Prepare parameters
        provider_idx = self._provider_combo.currentIndex()
        provider = "openai" if provider_idx == 1 else "whisper"

        options: dict[str, Any] = {
            "provider": provider,
            "mock": True,  # Running in mock mode by default to prevent torch blockings in UI
        }

        if provider == "whisper":
            options["model_size"] = self._model_combo.currentText()

        # Parse selected language
        lang_text = self._lang_combo.currentText()
        if lang_text != "Auto-Detect":
            options["language"] = lang_text.split(" ")[0]

        # Reset UI
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Preparing...")
        self._transcribe_btn.setEnabled(False)
        self._output_text.clear()

        # Start job
        self._vm.start_transcription("default", path, options)

    @Slot(str, float)
    def _on_progress(self, job_id: str, percent: float) -> None:
        self._progress_bar.setValue(int(percent))
        self._status_label.setText(f"Transcribing: {percent:.1f}%")

    @Slot(str, dict)
    def _on_completed(self, job_id: str, summary: dict[str, Any]) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Completed")
        self._status_label.setStyleSheet("color: #10B981; font-size: 12px;")
        self._transcribe_btn.setEnabled(True)

        # Output the result text
        result_text = (
            f"=== Transcription Completed ===\n"
            f"Language: {summary['language']}\n"
            f"Duration: {summary['duration']:.2f} seconds\n"
            f"Total Segments: {summary['segments_count']}\n"
            f"================================\n\n"
            f"{summary['full_text']}"
        )
        self._output_text.setPlainText(result_text)

    @Slot(str, str)
    def _on_failed(self, job_id: str, error_msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Failed")
        self._status_label.setStyleSheet("color: #EF4444; font-size: 12px;")
        self._transcribe_btn.setEnabled(True)
        self._output_text.setPlainText(f"Error: Transcription failed.\nReason: {error_msg}")


from typing import Optional
