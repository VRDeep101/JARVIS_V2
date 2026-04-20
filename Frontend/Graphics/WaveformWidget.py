# =============================================================
#  Frontend/Graphics/WaveformWidget.py - Voice Waveform
#
#  Kya karta:
#    - Audio-reactive waveform display
#    - When not active: gentle flat line
#    - When listening/speaking: animated wave
#    - Theme-aware color
# =============================================================

import math
import random
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QLinearGradient, QBrush
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class WaveformWidget(QWidget):
    """Audio-reactive waveform (simulated)."""
    
    FPS = 30
    BARS = 40
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        self.setMinimumHeight(40)
        self.setMinimumWidth(200)
        
        self.active = False         # True when listening or speaking
        self.bar_heights = [0.1] * self.BARS
        self.target_heights = [0.1] * self.BARS
        self.tick = 0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_anim)
        self.timer.start(1000 // self.FPS)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def set_active(self, active: bool):
        self.active = active
    
    def _tick_anim(self):
        self.tick += 1
        
        if self.active:
            # Generate new target heights
            for i in range(self.BARS):
                # Simulate voice frequency distribution
                center_bias = 1.0 - abs(i - self.BARS / 2) / (self.BARS / 2) * 0.5
                noise = random.random()
                wave = (math.sin(self.tick * 0.3 + i * 0.5) + 1) / 2
                self.target_heights[i] = min(1.0, max(0.1,
                    center_bias * (0.3 + noise * 0.5 + wave * 0.3)
                ))
        else:
            # Gentle idle animation
            for i in range(self.BARS):
                self.target_heights[i] = 0.08 + math.sin(self.tick * 0.05 + i * 0.3) * 0.04
        
        # Smooth towards target
        for i in range(self.BARS):
            diff = self.target_heights[i] - self.bar_heights[i]
            self.bar_heights[i] += diff * 0.3
        
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        primary = QColor(self.theme.primary)
        primary_soft = QColor(self.theme.primary_soft)
        
        bar_w = w / self.BARS * 0.7
        spacing = w / self.BARS
        
        # Gradient for bars
        gradient = QLinearGradient(0, h, 0, 0)
        gradient.setColorAt(0, primary)
        gradient.setColorAt(1, primary_soft)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        
        for i, bh in enumerate(self.bar_heights):
            bar_height = bh * h * 0.9
            x = i * spacing + (spacing - bar_w) / 2
            y = (h - bar_height) / 2
            painter.drawRoundedRect(
                int(x), int(y), int(bar_w), int(bar_height), 1, 1
            )
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(500, 200)
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    w = WaveformWidget(theme=neural_theme)
    layout.addWidget(w)
    
    btn = QPushButton("Toggle Active")
    btn.setStyleSheet("color: #00D4FF; background: transparent; border: 1px solid #00D4FF; padding: 6px;")
    state = [False]
    def toggle():
        state[0] = not state[0]
        w.set_active(state[0])
    btn.clicked.connect(toggle)
    layout.addWidget(btn)
    
    win.setCentralWidget(central)
    win.show()
    sys.exit(app.exec_())