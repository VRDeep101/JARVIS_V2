# =============================================================
#  Frontend/Graphics/BootAnimation.py - 3-sec Boot Sequence
#
#  Kya karta:
#    - Dramatic startup animation
#    - "JARVIS V2 INITIALIZING..." with progress
#    - Expanding circle reveal
#    - Emits signal when done
#    - 3 seconds total
# =============================================================

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QRadialGradient
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QProgressBar

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class BootAnimation(QWidget):
    """3-second boot animation."""
    
    boot_complete = pyqtSignal()
    
    FPS = 60
    DURATION_MS = 3000
    
    BOOT_STEPS = [
        (0,    "INITIALIZING CORE SYSTEMS..."),
        (500,  "LOADING MEMORY BANKS..."),
        (1000, "CALIBRATING VOICE SYSTEMS..."),
        (1500, "CONNECTING TO EXTERNAL APIs..."),
        (2000, "SYSTEMS ONLINE..."),
        (2500, "AT YOUR SERVICE, SIR."),
    ]
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        
        self.progress = 0.0
        self.elapsed_ms = 0
        self.tick = 0
        
        self._build_ui()
        
        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_anim)
        self.timer.start(1000 // self.FPS)
    
    def _build_ui(self):
        self.setStyleSheet(f"background-color: {self.theme.bg_main};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.addStretch()
        
        # Title
        self.title = QLabel("J.A.R.V.I.S")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet(f"""
            color: {self.theme.primary};
            font-family: "{self.theme.font_display}";
            font-size: 36pt;
            font-weight: bold;
            letter-spacing: 16px;
            background: transparent;
        """)
        layout.addWidget(self.title)
        
        subtitle = QLabel("V2.0")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            color: {self.theme.accent};
            font-size: 12pt;
            letter-spacing: 8px;
            background: transparent;
            padding-bottom: 30px;
        """)
        layout.addWidget(subtitle)
        
        # Status text
        self.status_label = QLabel(self.BOOT_STEPS[0][1])
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"""
            color: {self.theme.primary};
            font-family: "{self.theme.font_mono}";
            font-size: 11pt;
            letter-spacing: 1px;
            background: transparent;
        """)
        layout.addWidget(self.status_label)
        
        layout.addSpacing(40)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.theme.bg_input};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {self.theme.primary};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
    
    def _tick_anim(self):
        self.tick += 1
        self.elapsed_ms += 1000 // self.FPS
        
        # Update progress
        self.progress = min(100.0, (self.elapsed_ms / self.DURATION_MS) * 100)
        self.progress_bar.setValue(int(self.progress))
        
        # Update status text based on elapsed
        for step_ms, step_text in self.BOOT_STEPS:
            if self.elapsed_ms >= step_ms:
                current_text = step_text
        self.status_label.setText(current_text)
        
        # Check complete
        if self.elapsed_ms >= self.DURATION_MS:
            self.timer.stop()
            self.boot_complete.emit()
        
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        # Expanding circle effect
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        cx = self.width() / 2
        cy = self.height() / 2
        
        primary = QColor(self.theme.primary)
        
        # Expanding ripple rings
        for i in range(3):
            phase = (self.tick + i * 20) % 60
            radius = 30 + phase * 8
            alpha = max(0, 1.0 - phase / 60) * 0.3
            
            color = QColor(primary)
            color.setAlphaF(alpha)
            pen = QPen(color)
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                int(cx - radius), int(cy - radius),
                int(radius * 2), int(radius * 2),
            )
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.resize(900, 600)
    
    boot = BootAnimation(theme=neural_theme)
    boot.boot_complete.connect(lambda: print("Boot complete!"))
    win.setCentralWidget(boot)
    win.show()
    
    sys.exit(app.exec_())