# =============================================================
#  Frontend/Graphics/StatusTicker.py - Scrolling Status Text
#
#  Bottom ticker: "/// SYSTEMS ONLINE /// DEEP_ACTIVE ///"
#  Continuously scrolls right to left
# =============================================================

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class StatusTicker(QWidget):
    """Scrolling status text bar."""
    
    FPS = 30
    SCROLL_SPEED = 1.2  # pixels per frame
    
    DEFAULT_MESSAGES = [
        "SYSTEMS_ONLINE",
        "DEEP_ACTIVE",
        "J.A.R.V.I.S_V2",
        "NEURAL_READY",
        "PUNE_IN",
        "MEMORY_LOADED",
        "VOICE_STANDBY",
        "ALL_MODES_OPERATIONAL",
        "BUILT_BY_DEEP",
        "UPTIME_NOMINAL",
    ]
    
    def __init__(self, theme: Theme = None, messages=None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        
        self.messages = messages or self.DEFAULT_MESSAGES
        self.scroll_x = 0
        
        self.setFixedHeight(22)
        self.setMinimumWidth(200)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000 // self.FPS)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def set_messages(self, messages: list):
        self.messages = messages
    
    def _tick(self):
        self.scroll_x -= self.SCROLL_SPEED
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Build continuous text
        text = "  ///  ".join(self.messages) + "  ///  "
        
        # Font
        font = QFont(self.theme.font_mono, 9)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        painter.setFont(font)
        
        # Measure text
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        
        # Reset scroll when one full text passed
        if self.scroll_x <= -text_width:
            self.scroll_x = 0
        
        # Color
        color = QColor(self.theme.primary)
        color.setAlphaF(0.5)
        painter.setPen(QPen(color))
        
        # Draw text twice for seamless loop
        x = int(self.scroll_x)
        painter.drawText(x, 0, text_width, h, Qt.AlignVCenter, text)
        painter.drawText(x + text_width, 0, text_width, h, Qt.AlignVCenter, text)
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(800, 100)
    w = StatusTicker(theme=neural_theme)
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec_())