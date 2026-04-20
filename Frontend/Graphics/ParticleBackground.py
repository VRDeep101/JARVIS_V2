# =============================================================
#  Frontend/Graphics/ParticleBackground.py - Drifting Particles
#
#  Kya karta:
#    - Subtle particle drift in background
#    - Depth effect (different speeds/sizes)
#    - Theme-aware glow
#    - Transparent widget - overlay over other panels
# =============================================================

import random
import math
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QBrush
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class ParticleBackground(QWidget):
    """Subtle drifting particles background."""
    
    FPS = 30
    PARTICLE_COUNT = 40
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.particles = []
        self._init_particles()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000 // self.FPS)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def _init_particles(self):
        self.particles = []
        for _ in range(self.PARTICLE_COUNT):
            self.particles.append({
                "x": random.uniform(0, 1),
                "y": random.uniform(0, 1),
                "vy": random.uniform(-0.0015, -0.0002),
                "vx": random.uniform(-0.0005, 0.0005),
                "size": random.uniform(1.0, 2.8),
                "alpha": random.uniform(0.15, 0.5),
            })
    
    def _tick(self):
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            
            # Wrap around
            if p["y"] < -0.02:
                p["y"] = 1.02
                p["x"] = random.uniform(0, 1)
            if p["x"] < -0.02:
                p["x"] = 1.02
            elif p["x"] > 1.02:
                p["x"] = -0.02
        
        self.update()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
    
    def paintEvent(self, event):
        if self.width() == 0 or self.height() == 0:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        primary = QColor(self.theme.primary)
        painter.setPen(Qt.NoPen)
        
        for p in self.particles:
            color = QColor(primary)
            color.setAlphaF(p["alpha"])
            painter.setBrush(QBrush(color))
            
            x = p["x"] * w
            y = p["y"] * h
            size = p["size"]
            painter.drawEllipse(QPointF(x, y), size, size)
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(600, 400)
    w = ParticleBackground(theme=neural_theme)
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec_())