from typing import Optional
from PySide6.QtCore import Qt, Slot, QTimer
from app.infrastructure.config.translation import tr
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from app.ui.viewmodels.settings_viewmodel import SettingsViewModel


class SettingsView(QFrame):
    """Global configuration view managing themes, storage, API credentials and hardware configs."""

    def __init__(self, viewmodel: SettingsViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self._vm = viewmodel

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(20)

        # Header Title
        self._title = QLabel(tr("set.title"))
        self._title.setStyleSheet("font-size: 20px; font-weight: bold;")
        self._layout.addWidget(self._title)

        # Form Layout Container
        self._form = QWidget()
        self._form_layout = QFormLayout(self._form)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(16)
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 1. Theme Configuration
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["dark", "light"])
        self._theme_combo.setCurrentText(self._vm.theme_mode)
        self._form_layout.addRow(tr("set.theme"), self._theme_combo)

        # 1.5. Language Configuration
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["en", "vi"])
        self._lang_combo.setCurrentText(self._vm.language)
        self._form_layout.addRow(tr("set.lang"), self._lang_combo)

        # 2. Storage Directory picker
        self._storage_container = QWidget()
        self._storage_layout = QHBoxLayout(self._storage_container)
        self._storage_layout.setContentsMargins(0, 0, 0, 0)
        self._storage_layout.setSpacing(8)

        self._storage_input = QLineEdit()
        self._storage_input.setText(self._vm.storage_dir)
        self._storage_layout.addWidget(self._storage_input, stretch=1)

        self._storage_browse = QPushButton(tr("proj.browse"))
        self._storage_browse.clicked.connect(self._on_browse_storage)
        self._storage_layout.addWidget(self._storage_browse)

        self._form_layout.addRow(tr("set.storage"), self._storage_container)

        # 3. OpenAI API Key Input (with EchoMode masking)
        self._openai_container = QWidget()
        self._openai_layout = QHBoxLayout(self._openai_container)
        self._openai_layout.setContentsMargins(0, 0, 0, 0)
        self._openai_layout.setSpacing(8)

        self._openai_input = QLineEdit()
        self._openai_input.setText(self._vm.openai_api_key)
        self._openai_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_layout.addWidget(self._openai_input, stretch=1)

        self._openai_toggle = QPushButton("Show")
        self._openai_toggle.setFixedWidth(60)
        self._openai_toggle.clicked.connect(lambda: self._toggle_echo(self._openai_input, self._openai_toggle))
        self._openai_layout.addWidget(self._openai_toggle)

        self._form_layout.addRow(tr("set.openai"), self._openai_container)

        # 4. DeepSeek API Key Input
        self._deepseek_container = QWidget()
        self._deepseek_layout = QHBoxLayout(self._deepseek_container)
        self._deepseek_layout.setContentsMargins(0, 0, 0, 0)
        self._deepseek_layout.setSpacing(8)

        self._deepseek_input = QLineEdit()
        self._deepseek_input.setText(self._vm.deepseek_api_key)
        self._deepseek_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._deepseek_layout.addWidget(self._deepseek_input, stretch=1)

        self._deepseek_toggle = QPushButton("Show")
        self._deepseek_toggle.setFixedWidth(60)
        self._deepseek_toggle.clicked.connect(lambda: self._toggle_echo(self._deepseek_input, self._deepseek_toggle))
        self._deepseek_layout.addWidget(self._deepseek_toggle)

        self._form_layout.addRow(tr("set.deepseek"), self._deepseek_container)

        # 5. GPU Acceleration flag checkbox
        self._gpu_checkbox = QCheckBox("Enable GPU Acceleration (CUDA / DirectML)")
        self._gpu_checkbox.setChecked(self._vm.gpu_acceleration)
        self._form_layout.addRow(tr("set.gpu"), self._gpu_checkbox)

        self._layout.addWidget(self._form)

        # Actions Row
        self._actions_container = QWidget()
        self._actions_layout = QHBoxLayout(self._actions_container)
        self._actions_layout.setContentsMargins(0, 10, 0, 0)
        self._actions_layout.setSpacing(16)

        self._save_btn = QPushButton(tr("set.save_btn"))
        self._save_btn.setObjectName("primaryButton")
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._actions_layout.addWidget(self._save_btn)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #10B981; font-size: 13px; font-weight: bold;")
        self._actions_layout.addWidget(self._status_label)
        self._actions_layout.addStretch()

        self._layout.addWidget(self._actions_container)
        self._layout.addStretch()

    def _on_browse_storage(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Default Storage Folder", self._storage_input.text())
        if dir_path:
            self._storage_input.setText(dir_path)

    def _toggle_echo(self, line_edit: QLineEdit, button: QPushButton) -> None:
        if line_edit.echoMode() == QLineEdit.EchoMode.Password:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            button.setText("Hide")
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            button.setText("Show")

    def _on_save_clicked(self) -> None:
        theme = self._theme_combo.currentText()
        lang = self._lang_combo.currentText()
        storage = self._storage_input.text().strip()
        openai_key = self._openai_input.text().strip()
        deepseek_key = self._deepseek_input.text().strip()
        gpu_accel = self._gpu_checkbox.isChecked()

        # Update and save settings in database/yaml
        self._vm.save_settings(theme, lang, storage, openai_key, deepseek_key, gpu_accel)
        
        self._status_label.setText(tr("set.saved_msg"))
        # Auto-disappear status label after 5 seconds (5000ms)
        QTimer.singleShot(5000, lambda: self._status_label.clear())
