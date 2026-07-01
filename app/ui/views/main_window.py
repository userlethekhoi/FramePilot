
from loguru import logger
from app.infrastructure.config.translation import tr
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.application.di.container import Container
from app.ui.themes.engine import ThemeEngine
from app.ui.viewmodels.downloader_viewmodel import DownloaderViewModel
from app.ui.viewmodels.stt_viewmodel import SpeechToTextViewModel
from app.ui.viewmodels.enhancement_viewmodel import EnhancementViewModel
from app.ui.viewmodels.workflow_viewmodel import WorkflowViewModel
from app.ui.viewmodels.settings_viewmodel import SettingsViewModel
from app.ui.viewmodels.projects_viewmodel import ProjectsViewModel
from app.ui.views.downloader_view import DownloaderView
from app.ui.views.stt_view import SpeechToTextView
from app.ui.views.enhancement_view import EnhancementView
from app.ui.views.workflow_view import WorkflowView
from app.ui.views.settings_view import SettingsView
from app.ui.views.projects_view import ProjectsView


class NavigationSidebar(QFrame):
    """Left sidebar widget handling main application navigation actions."""

    def __init__(self, theme_engine: ThemeEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebarFrame")
        self._theme = theme_engine

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 24, 12, 12)
        self._layout.setSpacing(8)

        # Logo or branding header
        self._logo_label = QLabel("MediaFlow AI")
        self._logo_label.setStyleSheet("font-weight: bold; font-size: 16px; padding-bottom: 12px;")
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._logo_label)

        self.buttons: list[QPushButton] = []
        self._init_nav_buttons()

    def _init_nav_buttons(self) -> None:
        # Core navigation views
        nav_items = [
            (tr("nav.projects"), 0),
            (tr("nav.downloader"), 1),
            (tr("nav.transcribe"), 2),
            (tr("nav.enhancer"), 3),
            (tr("nav.workflow"), 4),
            (tr("nav.settings"), 5),
        ]

        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            # Match Figma sidebar buttons
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding: 10px 16px; border: none; border-radius: 6px; }"
                "QPushButton:checked { background-color: rgba(255, 255, 255, 0.08); font-weight: bold; }"
            )
            # Default check first button
            if idx == 0:
                btn.setChecked(True)

            self.buttons.append(btn)
            self._layout.addWidget(btn)

        self._layout.addStretch()


class MainWindow(QMainWindow):
    """Main window of the MediaFlow AI application, coordinating MVVM navigation and theme engine."""

    def __init__(self, container: Container) -> None:
        super().__init__()
        self._container = container
        self._theme = container.resolve(ThemeEngine)
        self.setWindowTitle("MediaFlow AI")
        self.resize(1200, 800)

        # Apply CSS/QSS styling
        self._apply_theme()
        self._theme.theme_changed.connect(self._on_theme_changed)

        # Central widget configuration
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)

        # Main Horizontal Layout
        self._main_layout = QHBoxLayout(self._central_widget)
        self._main_layout.setContentsMargins(16, 16, 16, 16)
        self._main_layout.setSpacing(16)

        # Sidebar navigation
        self._sidebar = NavigationSidebar(self._theme)
        self._main_layout.addWidget(self._sidebar)

        # Right Content Area using stacked layout
        self._content_stack = QStackedWidget()
        self._main_layout.addWidget(self._content_stack, stretch=1)

        self._init_pages()
        self._connect_nav_signals()

    def _init_pages(self) -> None:
        """Initializes navigation pages."""
        # Page 0: Projects Dashboard
        projects_vm = self._container.resolve(ProjectsViewModel)
        self._projects_page = ProjectsView(projects_vm)
        self._content_stack.addWidget(self._projects_page)

        # Page 1: Video/Image Downloader
        downloader_vm = self._container.resolve(DownloaderViewModel)
        self._downloader_page = DownloaderView(downloader_vm)
        self._content_stack.addWidget(self._downloader_page)

        # Page 2: Transcribe / Translation
        stt_vm = self._container.resolve(SpeechToTextViewModel)
        self._transcribe_page = SpeechToTextView(stt_vm)
        self._content_stack.addWidget(self._transcribe_page)

        # Page 3: Enhancement center
        enhancement_vm = self._container.resolve(EnhancementViewModel)
        self._enhancement_page = EnhancementView(enhancement_vm)
        self._content_stack.addWidget(self._enhancement_page)

        # Page 4: Workflows DAG
        workflow_vm = self._container.resolve(WorkflowViewModel)
        self._workflows_page = WorkflowView(workflow_vm)
        self._content_stack.addWidget(self._workflows_page)

        # Page 5: Settings Page
        settings_vm = self._container.resolve(SettingsViewModel)
        self._settings_page = SettingsView(settings_vm)
        self._content_stack.addWidget(self._settings_page)

    def _create_page(self, title_text: str) -> QWidget:
        """Helper to create standard stub pages for layout validation."""
        page = QFrame()
        page.setObjectName("panelFrame")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)

        label = QLabel(title_text)
        label.setStyleSheet("font-size: 18px; font-weight: 500;")
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(label)
        layout.addStretch()

        return page

    def _connect_nav_signals(self) -> None:
        """Toggles content stack view based on navigation button checked indices."""
        for i, btn in enumerate(self._sidebar.buttons):
            # Capture variable binding via lambda default parameters
            btn.clicked.connect(lambda checked, idx=i: self._navigate_to_page(idx))

    def _navigate_to_page(self, index: int) -> None:
        """Updates navigation layout selection and changes active stacked view index."""
        for i, btn in enumerate(self._sidebar.buttons):
            # Keep button states in sync
            btn.setChecked(i == index)

        self._content_stack.setCurrentIndex(index)
        logger.debug("Navigated to tab index: {}", index)

    def _apply_theme(self) -> None:
        """Loads compiled stylesheets from the theme engine."""
        stylesheet = self._theme.get_stylesheet()
        self.setStyleSheet(stylesheet)

    @Slot(str)
    def _on_theme_changed(self, mode: str) -> None:
        logger.info("Main Window applying updated theme stylesheet: {}", mode)
        self._apply_theme()
