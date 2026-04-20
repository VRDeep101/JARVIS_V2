# =============================================================
#  Frontend/Graphics/DataPanel.py - HUD Info Panels
#
#  Small info panels like image 3:
#    [ EEUU_054    COMPLETED ]
#    [ SPAIN_809   COMPLETED ]
#    [ NYKYO_945   LOADING...]
# =============================================================

import random
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class DataRow(QFrame):
    """Single data row with label + status."""
    
    def __init__(self, label: str, status: str, theme: Theme, is_loading: bool = False, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.is_loading = is_loading
        self.dots = 0
        
        self.setObjectName("data_row")
        self.setFixedHeight(32)
        self._apply_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)
        
        self.label = QLabel(label)
        self.label.setStyleSheet(f"""
            color: {theme.text_muted};
            font-family: "{theme.font_mono}";
            font-size: 9pt;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        # Status color based on type
        if is_loading:
            status_color = theme.warn
        elif "complete" in status.lower() or "active" in status.lower() or "online" in status.lower():
            status_color = theme.success
        else:
            status_color = theme.primary
        
        self.status = QLabel(status)
        self.status.setStyleSheet(f"""
            color: {status_color};
            font-family: "{theme.font_mono}";
            font-size: 9pt;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.status)
        
        # Loading animation
        if is_loading:
            self.base_status = status.replace("...", "")
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._tick_loading)
            self.timer.start(400)
    
    def _apply_style(self):
        self.setStyleSheet(f"""
            QFrame#data_row {{
                background-color: {self.theme.bg_input};
                border: 1px solid {self.theme.hex_with_alpha(self.theme.primary, 0.3)};
                border-radius: 3px;
            }}
        """)
    
    def _tick_loading(self):
        self.dots = (self.dots + 1) % 4
        self.status.setText(self.base_status + "." * self.dots)


class DataPanel(QWidget):
    """Panel with multiple status rows - image 3 style."""
    
    def __init__(self, theme: Theme = None, title: str = "STATUS", parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        self.title_text = title
        
        self.rows = []
        
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Title
        self.title = QLabel(self.title_text)
        self.title.setStyleSheet(f"""
            color: {self.theme.primary};
            font-family: "{self.theme.font_display}";
            font-size: 9pt;
            font-weight: bold;
            letter-spacing: 3px;
            background: transparent;
        """)
        layout.addWidget(self.title)
        
        # Container for rows
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(4)
        layout.addLayout(self.rows_layout)
        
        # Add default rows (will show interesting demo data)
        self._add_default_rows()
    
    def _add_default_rows(self):
        """Populate with demo-interesting status rows."""
        defaults = [
            ("CORE_SYS", "ONLINE", False),
            ("MEMORY", "LOADED", False),
            ("VOICE_IO", "READY", False),
            ("AI_LINK", "CONNECTED", False),
            ("PHISHING_D", "ACTIVE", False),
            ("LEARNING", "RUNNING", True),
        ]
        for label, status, loading in defaults:
            self.add_row(label, status, loading)
    
    def add_row(self, label: str, status: str, is_loading: bool = False):
        row = DataRow(label, status, self.theme, is_loading)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
    
    def clear_rows(self):
        for r in self.rows:
            r.deleteLater()
        self.rows = []
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.title.setStyleSheet(f"""
            color: {theme.primary};
            font-family: "{theme.font_display}";
            font-size: 9pt;
            font-weight: bold;
            letter-spacing: 3px;
            background: transparent;
        """)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(250, 300)
    w = DataPanel(theme=neural_theme, title="SYSTEMS")
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec_())