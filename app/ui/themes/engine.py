from loguru import logger
from PySide6.QtCore import QObject, Signal


class ThemeEngine(QObject):
    """Manages application design tokens, dynamic stylesheet compilation, and palette settings."""

    # Signal emitted when the current theme changes, allowing views to refresh their styles
    theme_changed = Signal(str)

    # Core premium design tokens (Figma, Notion, Arc style)
    PALETTES: dict[str, dict[str, str]] = {
        "dark": {
            "bg_primary": "#0B0C0E",  # Charcoal slate base
            "bg_secondary": "#16181C",  # Panel background
            "bg_tertiary": "#22252A",  # Button/Input background
            "border_color": "#2A2D35",  # Subtle boundaries
            "text_primary": "#F8FAFC",  # Sharp light text
            "text_secondary": "#94A3B8",  # Muted captions
            "accent_color": "#0066CC",  # Professional royal blue
            "accent_hover": "#0052A3",
            "accent_text": "#FFFFFF",
            "success": "#10B981",
            "warning": "#F59E0B",
            "danger": "#EF4444",
        },
        "light": {
            "bg_primary": "#F8FAFC",  # Crisp off-white
            "bg_secondary": "#FFFFFF",  # Elevated panels
            "bg_tertiary": "#F1F5F9",  # Inputs, standard buttons
            "border_color": "#E2E8F0",  # Soft boundaries
            "text_primary": "#0F172A",  # Deep slate text
            "text_secondary": "#64748B",  # Muted gray captions
            "accent_color": "#0066CC",  # Royal blue accent
            "accent_hover": "#0052A3",
            "accent_text": "#FFFFFF",
            "success": "#10B981",
            "warning": "#F59E0B",
            "danger": "#EF4444",
        },
    }

    def __init__(self, default_mode: str = "dark") -> None:
        super().__init__()
        self._current_mode = default_mode if default_mode in self.PALETTES else "dark"
        logger.info("ThemeEngine initialized with mode: {}", self._current_mode)

    @property
    def current_mode(self) -> str:
        return self._current_mode

    @current_mode.setter
    def current_mode(self, mode: str) -> None:
        if mode in self.PALETTES and mode != self._current_mode:
            self._current_mode = mode
            logger.info("Theme mode updated to: {}", mode)
            self.theme_changed.emit(mode)

    def get_token(self, name: str) -> str:
        """Retrieves a single color/design token value for the active theme."""
        palette = self.PALETTES.get(self._current_mode, self.PALETTES["dark"])
        return palette.get(name, "#000000")

    def get_stylesheet(self) -> str:
        """Compiles and returns a robust QSS (Qt Stylesheet) using active theme tokens."""
        p = self.PALETTES.get(self._current_mode, self.PALETTES["dark"])

        # Professional dark/light styles targeting core Qt widgets
        return f"""
        QMainWindow, QDialog {{
            background-color: {p["bg_primary"]};
            color: {p["text_primary"]};
        }}

        QWidget {{
            color: {p["text_primary"]};
            font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
            font-size: 13px;
        }}

        /* Panel surfaces */
        QFrame#panelFrame, QFrame#sidebarFrame {{
            background-color: {p["bg_secondary"]};
            border: 1px solid {p["border_color"]};
            border-radius: 8px;
        }}

        /* Scrollbars matching premium Figma interface */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {p["border_color"]};
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p["text_secondary"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}

        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {p["border_color"]};
            min-width: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {p["text_secondary"]};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            border: none;
            background: none;
            width: 0px;
        }}

        /* Text Input fields */
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
            background-color: {p["bg_tertiary"]};
            border: 1px solid {p["border_color"]};
            border-radius: 6px;
            padding: 8px 12px;
            color: {p["text_primary"]};
            selection-background-color: {p["accent_color"]};
            selection-color: {p["accent_text"]};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
            border: 1px solid {p["accent_color"]};
        }}

        /* Buttons styles */
        QPushButton {{
            background-color: {p["bg_tertiary"]};
            border: 1px solid {p["border_color"]};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 500;
            color: {p["text_primary"]};
        }}
        QPushButton:hover {{
            background-color: {p["border_color"]};
        }}
        QPushButton:pressed {{
            background-color: {p["bg_primary"]};
        }}
        QPushButton:disabled {{
            background-color: {p["bg_primary"]};
            color: {p["text_secondary"]};
            border: 1px solid {p["bg_primary"]};
        }}

        /* Primary Call-to-Action style */
        QPushButton#primaryButton {{
            background-color: {p["accent_color"]};
            border: 1px solid {p["accent_color"]};
            color: {p["accent_text"]};
        }}
        QPushButton#primaryButton:hover {{
            background-color: {p["accent_hover"]};
            border: 1px solid {p["accent_hover"]};
        }}
        QPushButton#primaryButton:pressed {{
            background-color: {p["bg_primary"]};
        }}

        /* Labels */
        QLabel {{
            color: {p["text_primary"]};
        }}
        QLabel#mutedLabel {{
            color: {p["text_secondary"]};
            font-size: 12px;
        }}

        /* Progress Bars */
        QProgressBar {{
            border: 1px solid {p["border_color"]};
            border-radius: 4px;
            text-align: center;
            background-color: {p["bg_primary"]};
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background-color: {p["accent_color"]};
            border-radius: 3px;
        }}

        /* Tab Widgets */
        QTabWidget::pane {{
            border: 1px solid {p["border_color"]};
            border-radius: 8px;
            background-color: {p["bg_secondary"]};
        }}
        QTabBar::tab {{
            background-color: {p["bg_primary"]};
            border: 1px solid {p["border_color"]};
            border-bottom-color: transparent;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            padding: 8px 16px;
            margin-right: 2px;
            color: {p["text_secondary"]};
        }}
        QTabBar::tab:selected, QTabBar::tab:hover {{
            background-color: {p["bg_secondary"]};
            color: {p["text_primary"]};
        }}
        """
