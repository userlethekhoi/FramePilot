from typing import Any, Dict, Optional
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from loguru import logger
from app.ui.viewmodels.stt_viewmodel import SpeechToTextViewModel
from app.infrastructure.config.translation import tr


class SpeechToTextView(QFrame):
    """Speech recognition, subtitle translation, and voice synthesis (dubbing) workspace panel."""

    def __init__(self, viewmodel: SpeechToTextViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self._vm = viewmodel
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(16)

        # Header Title
        self._title = QLabel(tr("stt.title"))
        self._title.setStyleSheet("font-size: 20px; font-weight: bold;")
        self._layout.addWidget(self._title)

        # Tab Widget
        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs)

        self._setup_transcription_tab()
        self._setup_translation_dub_tab()

        # Bind View Model signals
        self._vm.transcription_progress.connect(self._on_transcribe_progress)
        self._vm.transcription_completed.connect(self._on_transcribe_completed)
        self._vm.transcription_failed.connect(self._on_transcribe_failed)

        self._vm.translation_progress.connect(self._on_translate_progress)
        self._vm.translation_completed.connect(self._on_translate_completed)
        self._vm.translation_failed.connect(self._on_translate_failed)

        self._vm.synthesis_progress.connect(self._on_synthesis_progress)
        self._vm.synthesis_completed.connect(self._on_synthesis_completed)
        self._vm.synthesis_failed.connect(self._on_synthesis_failed)

    def _setup_transcription_tab(self) -> None:
        """Sets up the Speech-to-Text transcription interface tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # 1. Media File Picker
        file_container = QWidget()
        file_layout = QHBoxLayout(file_container)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(12)

        file_label = QLabel(tr("stt.file_lbl"))
        file_layout.addWidget(file_label)

        self._media_path_input = QLineEdit()
        self._media_path_input.setPlaceholderText("Select video or audio file path (.wav, .mp3, .mp4, .mkv)...")
        file_layout.addWidget(self._media_path_input, stretch=1)

        self._media_browse_btn = QPushButton("Browse")
        self._media_browse_btn.clicked.connect(self._on_media_browse_clicked)
        file_layout.addWidget(self._media_browse_btn)
        layout.addWidget(file_container)

        # 2. Options selector
        opt_container = QWidget()
        opt_layout = QHBoxLayout(opt_container)
        opt_layout.setContentsMargins(0, 0, 0, 0)
        opt_layout.setSpacing(16)

        prov_label = QLabel(tr("stt.provider_lbl"))
        opt_layout.addWidget(prov_label)

        self._transcribe_prov_combo = QComboBox()
        self._transcribe_prov_combo.addItems([
            "Local Whisper (Offline)",
            "OpenAI Whisper (Cloud)",
        ])
        self._transcribe_prov_combo.currentIndexChanged.connect(self._on_transcribe_provider_changed)
        opt_layout.addWidget(self._transcribe_prov_combo)

        self._model_label = QLabel(tr("stt.model_lbl"))
        opt_layout.addWidget(self._model_label)

        self._model_combo = QComboBox()
        self._model_combo.addItems(["tiny", "base", "small", "medium", "large"])
        self._model_combo.setCurrentText("base")
        opt_layout.addWidget(self._model_combo)

        lang_label = QLabel(tr("stt.lang_lbl"))
        opt_layout.addWidget(lang_label)

        self._transcribe_lang_combo = QComboBox()
        self._transcribe_lang_combo.addItems([
            "Auto-Detect",
            "en (English)",
            "vi (Vietnamese)",
            "zh (Chinese)",
            "ja (Japanese)",
            "fr (French)",
            "de (German)",
            "es (Spanish)",
        ])
        opt_layout.addWidget(self._transcribe_lang_combo)

        opt_layout.addStretch()
        layout.addWidget(opt_container)

        # 3. Action / Progress
        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(16)

        self._transcribe_btn = QPushButton(tr("stt.btn"))
        self._transcribe_btn.setObjectName("primaryButton")
        self._transcribe_btn.clicked.connect(self._on_transcribe_clicked)
        action_layout.addWidget(self._transcribe_btn)

        self._transcribe_progress_bar = QProgressBar()
        self._transcribe_progress_bar.setRange(0, 100)
        self._transcribe_progress_bar.setValue(0)
        self._transcribe_progress_bar.setFixedHeight(8)
        self._transcribe_progress_bar.setTextVisible(False)
        self._transcribe_progress_bar.setVisible(False)
        action_layout.addWidget(self._transcribe_progress_bar, stretch=1)

        self._transcribe_status_lbl = QLabel("")
        self._transcribe_status_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        action_layout.addWidget(self._transcribe_status_lbl)
        layout.addWidget(action_container)

        # 4. Transcribed output log
        out_lbl = QLabel("Transcription Output Log")
        out_lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(out_lbl)

        self._transcribe_output_text = QPlainTextEdit()
        self._transcribe_output_text.setReadOnly(True)
        self._transcribe_output_text.setPlaceholderText("Transcribed text and subtitle details will display here...")
        self._transcribe_output_text.setStyleSheet(
            "QPlainTextEdit { font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }"
        )
        layout.addWidget(self._transcribe_output_text, stretch=1)

        self._tabs.addTab(tab, "1. Transcription (STT)")

    def _setup_translation_dub_tab(self) -> None:
        """Sets up the Subtitle Translation and TTS voice synthesis tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # 1. Subtitle File Picker
        file_container = QWidget()
        file_layout = QHBoxLayout(file_container)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(12)

        file_label = QLabel(tr("stt.sub_lbl"))
        file_layout.addWidget(file_label)

        self._sub_path_input = QLineEdit()
        self._sub_path_input.setPlaceholderText("Select source subtitle file (.srt, .vtt)...")
        file_layout.addWidget(self._sub_path_input, stretch=1)

        self._sub_browse_btn = QPushButton("Browse")
        self._sub_browse_btn.clicked.connect(self._on_sub_browse_clicked)
        file_layout.addWidget(self._sub_browse_btn)
        layout.addWidget(file_container)

        # 2. Translation Options
        trans_container = QWidget()
        trans_layout = QHBoxLayout(trans_container)
        trans_layout.setContentsMargins(0, 0, 0, 0)
        trans_layout.setSpacing(16)

        trans_prov_label = QLabel(tr("stt.trans_lbl"))
        trans_layout.addWidget(trans_prov_label)

        self._trans_prov_combo = QComboBox()
        self._trans_prov_combo.addItems([
            "Google Translate (Free)",
            "OpenAI GPT-4o (Cloud)",
        ])
        trans_layout.addWidget(self._trans_prov_combo)

        target_lang_label = QLabel(tr("stt.target_lang_lbl"))
        trans_layout.addWidget(target_lang_label)

        self._target_lang_combo = QComboBox()
        self._target_lang_combo.addItems(["en", "vi", "fr", "es", "de", "ja", "zh"])
        self._target_lang_combo.setCurrentText("vi")
        trans_layout.addWidget(self._target_lang_combo)

        self._translate_btn = QPushButton(tr("stt.trans_btn"))
        self._translate_btn.clicked.connect(self._on_translate_clicked)
        trans_layout.addWidget(self._translate_btn)

        trans_layout.addStretch()
        layout.addWidget(trans_container)

        # 3. TTS Synthesis Options
        tts_container = QWidget()
        tts_layout = QHBoxLayout(tts_container)
        tts_layout.setContentsMargins(0, 0, 0, 0)
        tts_layout.setSpacing(16)

        tts_prov_label = QLabel(tr("stt.tts_lbl"))
        tts_layout.addWidget(tts_prov_label)

        self._tts_prov_combo = QComboBox()
        self._tts_prov_combo.addItems([
            "Local Offline Engine",
            "OpenAI TTS (Cloud)",
        ])
        self._tts_prov_combo.currentIndexChanged.connect(self._on_tts_provider_changed)
        tts_layout.addWidget(self._tts_prov_combo)

        self._voice_label = QLabel(tr("stt.voice_lbl"))
        tts_layout.addWidget(self._voice_label)

        self._voice_combo = QComboBox()
        self._voice_combo.addItems(["alloy", "echo", "fable", "onyx", "nova", "shimmer"])
        self._voice_combo.setCurrentText("alloy")
        tts_layout.addWidget(self._voice_combo)

        self._dub_btn = QPushButton(tr("stt.dub_btn"))
        self._dub_btn.setObjectName("primaryButton")
        self._dub_btn.clicked.connect(self._on_dub_clicked)
        tts_layout.addWidget(self._dub_btn)

        tts_layout.addStretch()
        layout.addWidget(tts_container)

        # 4. Action progress / status
        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(16)

        self._dub_progress_bar = QProgressBar()
        self._dub_progress_bar.setRange(0, 100)
        self._dub_progress_bar.setValue(0)
        self._dub_progress_bar.setFixedHeight(8)
        self._dub_progress_bar.setTextVisible(False)
        self._dub_progress_bar.setVisible(False)
        action_layout.addWidget(self._dub_progress_bar, stretch=1)

        self._dub_status_lbl = QLabel("")
        self._dub_status_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        action_layout.addWidget(self._dub_status_lbl)
        layout.addWidget(action_container)

        # 5. Output display
        result_lbl = QLabel("Execution Log & Outputs")
        result_lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(result_lbl)

        self._dub_output_text = QPlainTextEdit()
        self._dub_output_text.setReadOnly(True)
        self._dub_output_text.setPlaceholderText("Subtitles translation and voice synthesis paths will display here...")
        self._dub_output_text.setStyleSheet(
            "QPlainTextEdit { font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }"
        )
        layout.addWidget(self._dub_output_text, stretch=1)

        self._tabs.addTab(tab, "2. Translation & Dubbing (TTS)")

    def _on_media_browse_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio/Video file",
            "",
            "Media Files (*.mp3 *.wav *.mp4 *.mkv *.avi *.mov *.webm);;All Files (*)",
        )
        if file_path:
            self._media_path_input.setText(file_path)

    def _on_sub_browse_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Subtitle file",
            "",
            "Subtitles (*.srt *.vtt);;All Files (*)",
        )
        if file_path:
            self._sub_path_input.setText(file_path)

    def _on_transcribe_provider_changed(self, index: int) -> None:
        is_local = index == 0
        self._model_label.setVisible(is_local)
        self._model_combo.setVisible(is_local)

    def _on_tts_provider_changed(self, index: int) -> None:
        is_openai = index == 1
        self._voice_label.setVisible(is_openai)
        self._voice_combo.setVisible(is_openai)

    def _on_transcribe_clicked(self) -> None:
        path = self._media_path_input.text().strip()
        if not path:
            self._transcribe_output_text.setPlainText("Error: Please select a valid media file path.")
            return

        provider_idx = self._transcribe_prov_combo.currentIndex()
        provider = "openai" if provider_idx == 1 else "whisper"

        options: dict[str, Any] = {
            "provider": provider,
            "mock": True,
        }

        if provider == "whisper":
            options["model_size"] = self._model_combo.currentText()

        lang_text = self._transcribe_lang_combo.currentText()
        if lang_text != "Auto-Detect":
            options["language"] = lang_text.split(" ")[0]

        self._transcribe_progress_bar.setValue(0)
        self._transcribe_progress_bar.setVisible(True)
        self._transcribe_status_lbl.setText("Preparing...")
        self._transcribe_btn.setEnabled(False)
        self._transcribe_output_text.clear()

        self._vm.start_transcription("default", path, options)

    def _on_translate_clicked(self) -> None:
        path = self._sub_path_input.text().strip()
        if not path:
            self._dub_output_text.setPlainText("Error: Please select a subtitle file first.")
            return

        target_lang = self._target_lang_combo.currentText()
        provider_idx = self._trans_prov_combo.currentIndex()
        provider = "gpt" if provider_idx == 1 else "google"

        options: dict[str, Any] = {
            "provider": provider,
            "mock": True,
        }

        self._dub_progress_bar.setValue(0)
        self._dub_progress_bar.setVisible(True)
        self._dub_status_lbl.setText("Translating...")
        self._translate_btn.setEnabled(False)
        self._dub_output_text.clear()

        self._vm.translate_subtitles("default", path, target_lang, options)

    def _on_dub_clicked(self) -> None:
        path = self._sub_path_input.text().strip()
        if not path:
            self._dub_output_text.setPlainText("Error: Please select a subtitle file first.")
            return

        provider_idx = self._tts_prov_combo.currentIndex()
        provider = "openai" if provider_idx == 1 else "local"
        voice_id = self._voice_combo.currentText() if provider == "openai" else ""

        options: dict[str, Any] = {
            "provider": provider,
            "mock": True,
        }

        self._dub_progress_bar.setValue(0)
        self._dub_progress_bar.setVisible(True)
        self._dub_status_lbl.setText("Synthesizing...")
        self._dub_btn.setEnabled(False)
        self._dub_output_text.clear()

        self._vm.synthesize_voice("default", path, voice_id, options)

    # Transcription Slots
    @Slot(str, float)
    def _on_transcribe_progress(self, job_id: str, percent: float) -> None:
        self._transcribe_progress_bar.setValue(int(percent))
        self._transcribe_status_lbl.setText(f"Transcribing: {percent:.1f}%")

    @Slot(str, dict)
    def _on_transcribe_completed(self, job_id: str, summary: dict[str, Any]) -> None:
        self._transcribe_progress_bar.setVisible(False)
        self._transcribe_status_lbl.setText("Completed")
        self._transcribe_status_lbl.setStyleSheet("color: #10B981; font-size: 12px;")
        self._transcribe_btn.setEnabled(True)

        result_text = (
            f"=== Transcription Completed ===\n"
            f"Language: {summary['language']}\n"
            f"Duration: {summary['duration']:.2f} seconds\n"
            f"Total Segments: {summary['segments_count']}\n"
            f"================================\n\n"
            f"{summary['full_text']}"
        )
        self._transcribe_output_text.setPlainText(result_text)

    @Slot(str, str)
    def _on_transcribe_failed(self, job_id: str, error_msg: str) -> None:
        self._transcribe_progress_bar.setVisible(False)
        self._transcribe_status_lbl.setText("Failed")
        self._transcribe_status_lbl.setStyleSheet("color: #EF4444; font-size: 12px;")
        self._transcribe_btn.setEnabled(True)
        self._transcribe_output_text.setPlainText(f"Error: Transcription failed.\nReason: {error_msg}")

    # Translation Slots
    @Slot(str, float)
    def _on_translate_progress(self, job_id: str, percent: float) -> None:
        self._dub_progress_bar.setValue(int(percent))
        self._dub_status_lbl.setText(f"Translating: {percent:.1f}%")

    @Slot(str, str)
    def _on_translate_completed(self, job_id: str, output_path: str) -> None:
        self._dub_progress_bar.setVisible(False)
        self._dub_status_lbl.setText("Translation Completed")
        self._dub_status_lbl.setStyleSheet("color: #10B981; font-size: 12px;")
        self._translate_btn.setEnabled(True)

        self._dub_output_text.setPlainText(
            f"=== Subtitle Translation Completed ===\n"
            f"Exported Translated Subtitles to:\n"
            f"{output_path}"
        )
        # Update Subtitle Input to translated output for quick dubbing workflow
        self._sub_path_input.setText(output_path)

    @Slot(str, str)
    def _on_translate_failed(self, job_id: str, error_msg: str) -> None:
        self._dub_progress_bar.setVisible(False)
        self._dub_status_lbl.setText("Translation Failed")
        self._dub_status_lbl.setStyleSheet("color: #EF4444; font-size: 12px;")
        self._translate_btn.setEnabled(True)
        self._dub_output_text.setPlainText(f"Error: Subtitles translation failed.\nReason: {error_msg}")

    # Voice Synthesis Slots
    @Slot(str, float)
    def _on_synthesis_progress(self, job_id: str, percent: float) -> None:
        self._dub_progress_bar.setValue(int(percent))
        self._dub_status_lbl.setText(f"Dubbing: {percent:.1f}%")

    @Slot(str, str)
    def _on_synthesis_completed(self, job_id: str, output_path: str) -> None:
        self._dub_progress_bar.setVisible(False)
        self._dub_status_lbl.setText("Dubbing Synthesized")
        self._dub_status_lbl.setStyleSheet("color: #10B981; font-size: 12px;")
        self._dub_btn.setEnabled(True)

        self._dub_output_text.setPlainText(
            f"=== Voice Synthesis Completed ===\n"
            f"Exported Unified Audio Dubbing Track to:\n"
            f"{output_path}"
        )

    @Slot(str, str)
    def _on_synthesis_failed(self, job_id: str, error_msg: str) -> None:
        self._dub_progress_bar.setVisible(False)
        self._dub_status_lbl.setText("Dubbing Failed")
        self._dub_status_lbl.setStyleSheet("color: #EF4444; font-size: 12px;")
        self._dub_btn.setEnabled(True)
        self._dub_output_text.setPlainText(f"Error: Voice synthesis failed.\nReason: {error_msg}")
