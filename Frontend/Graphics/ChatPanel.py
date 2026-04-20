# =============================================================
#  Frontend/Graphics/ChatPanel.py - Holographic Chat
#
#  Kya karta:
#    - Scrollable chat display
#    - User + Jarvis message bubbles (different styles)
#    - Typewriter effect for Jarvis messages (letter-by-letter)
#    - Theme-aware colors
#    - Auto-scroll to bottom on new message
#    - Fade-in animation for new messages
#
#  Usage:
#    chat = ChatPanel(theme=neural_theme)
#    chat.add_user("hello jarvis")
#    chat.add_jarvis("At your service, Sir.")
# =============================================================

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QGraphicsOpacityEffect,
)

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


# =============================================================
#  Single message bubble
# =============================================================
class MessageBubble(QFrame):
    """One chat message (user or Jarvis)."""
    
    def __init__(self, text: str, is_user: bool, theme: Theme, typewriter: bool = False, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.is_user = is_user
        self.full_text = text
        
        self.setObjectName("bubble")
        self._apply_style()
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        
        # Label
        self.label = QLabel("" if typewriter else text)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.label.setStyleSheet(f"""
            color: {theme.text_primary};
            background: transparent;
            border: none;
            font-family: "{theme.font_main}";
            font-size: 10pt;
        """)
        layout.addWidget(self.label)
        
        # Typewriter effect for Jarvis messages
        self._typewriter_idx = 0
        if typewriter and not is_user:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick_typewriter)
            self._timer.start(18)  # char-per-ms
        
        # Fade-in
        self._apply_fade_in()
    
    def _apply_style(self):
        t = self.theme
        if self.is_user:
            # User bubble: subtle, aligned right
            self.setStyleSheet(f"""
                QFrame#bubble {{
                    background-color: {t.hex_with_alpha(t.primary, 0.08)};
                    border: 1px solid {t.hex_with_alpha(t.primary, 0.3)};
                    border-radius: 10px;
                }}
            """)
        else:
            # Jarvis bubble: brighter
            self.setStyleSheet(f"""
                QFrame#bubble {{
                    background-color: {t.bg_panel};
                    border: 1px solid {t.hex_with_alpha(t.primary, 0.5)};
                    border-radius: 10px;
                }}
            """)
    
    def _tick_typewriter(self):
        if self._typewriter_idx >= len(self.full_text):
            self._timer.stop()
            return
        self._typewriter_idx += 1
        self.label.setText(self.full_text[:self._typewriter_idx])
    
    def _apply_fade_in(self):
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(350)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_anim.start()


# =============================================================
#  Chat container
# =============================================================
class ChatPanel(QWidget):
    """Scrollable holographic chat."""
    
    message_added = pyqtSignal(str, bool)  # text, is_user
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        
        self._setup_ui()
        self.setMinimumWidth(350)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        self.header = QLabel("CHAT")
        self.header.setStyleSheet(f"""
            color: {self.theme.primary};
            font-family: "{self.theme.font_display}";
            font-size: 10pt;
            font-weight: bold;
            letter-spacing: 3px;
            padding: 8px 12px;
            border-bottom: 1px solid {self.theme.border};
        """)
        layout.addWidget(self.header)
        
        # Scrollable area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {self.theme.bg_panel};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.theme.hex_with_alpha(self.theme.primary, 0.5)};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none; background: none; height: 0;
            }}
        """)
        
        # Content widget
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch()  # push bubbles to bottom
        
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)
    
    # =========================================================
    #  Public API
    # =========================================================
    def add_user(self, text: str):
        self._add_bubble(text, is_user=True, typewriter=False)
        self.message_added.emit(text, True)
    
    def add_jarvis(self, text: str, typewriter: bool = True):
        self._add_bubble(text, is_user=False, typewriter=typewriter)
        self.message_added.emit(text, False)
    
    def _add_bubble(self, text: str, is_user: bool, typewriter: bool):
        bubble = MessageBubble(text, is_user=is_user, theme=self.theme, typewriter=typewriter)
        
        # Wrap in a row to align left/right
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        
        if is_user:
            row.addStretch()
            row.addWidget(bubble, stretch=0)
        else:
            row.addWidget(bubble, stretch=0)
            row.addStretch()
        
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row_widget.setLayout(row)
        
        # Insert above the final stretch
        count = self.content_layout.count()
        self.content_layout.insertWidget(count - 1, row_widget)
        
        # Auto-scroll
        QTimer.singleShot(50, self._scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        scrollbar = self.scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear(self):
        """Remove all bubbles."""
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.setStyleSheet(f"background-color: {theme.bg_panel};")
        self.header.setStyleSheet(f"""
            color: {theme.primary};
            font-family: "{theme.font_display}";
            font-size: 10pt;
            font-weight: bold;
            letter-spacing: 3px;
            padding: 8px 12px;
            border-bottom: 1px solid {theme.border};
        """)


# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("ChatPanel Test")
    win.resize(500, 700)
    win.setStyleSheet("background-color: #060B14;")
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    chat = ChatPanel(theme=neural_theme)
    layout.addWidget(chat)
    
    # Add some sample messages
    chat.add_user("hello jarvis")
    chat.add_jarvis("At your service, Sir. How can I help you today?")
    chat.add_user("what's the weather in pune")
    chat.add_jarvis("Currently 28 degrees in Pune, Sir. Partly cloudy.")
    
    # Test button
    btn = QPushButton("Add more messages")
    btn.setStyleSheet("color: #00D4FF; background: transparent; border: 1px solid #00D4FF; padding: 8px;")
    counter = [0]
    def add():
        counter[0] += 1
        chat.add_user(f"Test message #{counter[0]}")
        QTimer.singleShot(500, lambda: chat.add_jarvis(
            f"Response number {counter[0]}. This is a slightly longer message to test wrapping and the typewriter effect in action."
        ))
    btn.clicked.connect(add)
    layout.addWidget(btn)
    
    win.setCentralWidget(central)
    win.show()
    
    sys.exit(app.exec_())