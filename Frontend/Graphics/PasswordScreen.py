# =============================================================
#  Frontend/Graphics/PasswordScreen.py - REDESIGNED
#  Companion Password Entry (fixed layout)
# =============================================================

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFrame, QSizePolicy,
)

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.companion_theme import companion_theme


class PasswordScreen(QWidget):
    """Password entry overlay for Companion mode - redesigned."""
    
    password_submitted = pyqtSignal(str)
    cancelled = pyqtSignal()
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or companion_theme
        
        self.entered = ""
        self.max_length = 4
        
        self._build_ui()
    
    def _build_ui(self):
        # Full-screen dark overlay
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme.bg_main};
            }}
        """)
        
        # Outer layout centers the card
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()
        
        # Horizontal centering row
        card_row = QHBoxLayout()
        card_row.addStretch()
        
        # ============ CARD ============
        card = QFrame()
        card.setObjectName("pw_card")
        card.setFixedSize(440, 640)   # fixed size - prevents overlap
        card.setStyleSheet(f"""
            QFrame#pw_card {{
                background-color: {self.theme.bg_panel};
                border: 2px solid {self.theme.primary};
                border-radius: 20px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(35, 30, 35, 30)
        card_layout.setSpacing(18)
        
        # --- Title ---
        title = QLabel("COMPANION MODE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            color: {self.theme.primary};
            font-family: "{self.theme.font_display}";
            font-size: 16pt;
            font-weight: bold;
            letter-spacing: 6px;
            background: transparent;
            border: none;
            padding: 4px;
        """)
        card_layout.addWidget(title)
        
        subtitle = QLabel("Enter access code, Deep")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            color: {self.theme.accent};
            font-size: 11pt;
            background: transparent;
            border: none;
            padding-bottom: 4px;
        """)
        card_layout.addWidget(subtitle)
        
        # --- Display field (dots for entered digits) ---
        self.display = QLabel("")
        self.display.setAlignment(Qt.AlignCenter)
        self.display.setFixedHeight(70)
        self.display.setStyleSheet(f"""
            color: {self.theme.primary};
            font-size: 36pt;
            font-weight: bold;
            letter-spacing: 20px;
            background: {self.theme.bg_input};
            border: 1px solid {self.theme.border};
            border-radius: 10px;
        """)
        card_layout.addWidget(self.display)
        
        # --- Numpad (proper grid) ---
        numpad_wrapper = QWidget()
        numpad_wrapper.setStyleSheet("background: transparent;")
        grid = QGridLayout(numpad_wrapper)
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)
        
        # Layout:
        # 1 2 3
        # 4 5 6
        # 7 8 9
        # ← 0 ✓
        buttons = [
            ("1", 0, 0, "digit"), ("2", 0, 1, "digit"), ("3", 0, 2, "digit"),
            ("4", 1, 0, "digit"), ("5", 1, 1, "digit"), ("6", 1, 2, "digit"),
            ("7", 2, 0, "digit"), ("8", 2, 1, "digit"), ("9", 2, 2, "digit"),
            ("←", 3, 0, "back"), ("0", 3, 1, "digit"), ("✓", 3, 2, "submit"),
        ]
        
        for label, row, col, kind in buttons:
            btn = QPushButton(label)
            btn.setFixedSize(105, 60)
            
            if kind == "back":
                color = self.theme.warn
                btn.clicked.connect(self._backspace)
            elif kind == "submit":
                color = self.theme.success
                btn.clicked.connect(self._submit)
            else:
                color = self.theme.primary
                btn.clicked.connect(lambda _, d=label: self._digit(d))
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {self.theme.hex_with_alpha(color, 0.1)};
                    color: {color};
                    border: 1px solid {self.theme.hex_with_alpha(color, 0.5)};
                    border-radius: 10px;
                    font-size: 18pt;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {self.theme.hex_with_alpha(color, 0.25)};
                    border: 1px solid {color};
                }}
                QPushButton:pressed {{
                    background: {self.theme.hex_with_alpha(color, 0.4)};
                }}
            """)
            grid.addWidget(btn, row, col)
        
        card_layout.addWidget(numpad_wrapper, alignment=Qt.AlignCenter)
        
        # --- Voice hint ---
        self.voice_label = QLabel("🎤  Or say the code")
        self.voice_label.setAlignment(Qt.AlignCenter)
        self.voice_label.setStyleSheet(f"""
            color: {self.theme.text_muted};
            font-size: 10pt;
            background: transparent;
            border: none;
            padding-top: 4px;
        """)
        card_layout.addWidget(self.voice_label)
        
        # --- Status (error/success messages) ---
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(22)
        self.status_label.setStyleSheet(f"""
            color: {self.theme.error};
            font-size: 10pt;
            background: transparent;
            border: none;
        """)
        card_layout.addWidget(self.status_label)
        
        # --- Cancel button ---
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.theme.text_muted};
                border: 1px solid {self.theme.border};
                border-radius: 8px;
                padding: 8px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                color: {self.theme.text_primary};
                border: 1px solid {self.theme.text_muted};
            }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        card_layout.addWidget(cancel_btn)
        
        # ============ END CARD ============
        
        card_row.addWidget(card)
        card_row.addStretch()
        
        outer.addLayout(card_row)
        outer.addStretch()
    
    # =========================================================
    #  Input handlers
    # =========================================================
    def _digit(self, digit: str):
        if len(self.entered) < self.max_length:
            self.entered += digit
            self._update_display()
    
    def _backspace(self):
        if self.entered:
            self.entered = self.entered[:-1]
            self._update_display()
    
    def _submit(self):
        if not self.entered:
            return
        self.password_submitted.emit(self.entered)
    
    def _cancel(self):
        self.entered = ""
        self._update_display()
        self.cancelled.emit()
    
    def _update_display(self):
        self.display.setText("•" * len(self.entered))
    
    # =========================================================
    #  External API
    # =========================================================
    def show_error(self, msg: str):
        self.status_label.setStyleSheet(f"""
            color: {self.theme.error};
            font-size: 10pt;
            background: transparent;
            border: none;
        """)
        self.status_label.setText(msg)
        # Flash display red briefly
        orig_style = self.display.styleSheet()
        error_style = orig_style.replace(self.theme.border, self.theme.error)
        self.display.setStyleSheet(error_style)
        QTimer.singleShot(500, lambda: self.display.setStyleSheet(orig_style))
        # Clear entered
        self.entered = ""
        self._update_display()
    
    def show_success(self):
        self.status_label.setStyleSheet(f"""
            color: {self.theme.success};
            font-size: 10pt;
            background: transparent;
            border: none;
        """)
        self.status_label.setText("Access granted.")
    
    def reset(self):
        self.entered = ""
        self._update_display()
        self.status_label.setText("")
    
    def set_theme(self, theme: Theme):
        self.theme = theme


# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(800, 800)
    
    screen = PasswordScreen(theme=companion_theme)
    
    def on_submit(pw):
        print(f"Entered: {pw}")
        if pw == "1406":
            screen.show_success()
        else:
            screen.show_error("Wrong code, Deep. Try again.")
    
    def on_cancel():
        print("Cancelled")
    
    screen.password_submitted.connect(on_submit)
    screen.cancelled.connect(on_cancel)
    
    win.setCentralWidget(screen)
    win.show()
    sys.exit(app.exec_())