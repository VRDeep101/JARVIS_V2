# =============================================================
#  Frontend/Graphics/RadarWidget.py - Size-optimized
# =============================================================

import math
import random
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class RadarWidget(QWidget):
    FPS = 30
    SWEEP_SPEED = 2.0
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        self.setMinimumSize(100, 100)  # smaller min
        
        self.sweep_angle = 0
        self.tick = 0
        self.blips = []
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_anim)
        self.timer.start(1000 // self.FPS)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def _tick_anim(self):
        self.tick += 1
        self.sweep_angle += self.SWEEP_SPEED
        if self.sweep_angle >= 360:
            self.sweep_angle -= 360
        
        if random.random() < 0.02:
            self.blips.append([
                random.uniform(0, 360),
                random.uniform(0.3, 0.9),
                50,
            ])
        
        self.blips = [
            [b[0], b[1], b[2] - 1]
            for b in self.blips if b[2] > 0
        ]
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        
        # Reduced radius - fits in box with margin
        radius = min(w, h) * 0.40
        
        primary = QColor(self.theme.primary)
        
        # Concentric circles
        for frac in [0.33, 0.66, 1.0]:
            color = QColor(primary)
            color.setAlphaF(0.3)
            pen = QPen(color)
            pen.setWidthF(0.8)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), radius * frac, radius * frac)
        
        # Cross hairs
        cross_color = QColor(primary)
        cross_color.setAlphaF(0.2)
        pen = QPen(cross_color)
        pen.setWidthF(0.8)
        painter.setPen(pen)
        painter.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))
        painter.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))
        
        # Sweep trail
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self.sweep_angle - 90)
        
        trail_color = QColor(primary)
        for i in range(50):
            alpha = (1 - i / 50) * 0.35
            trail_color.setAlphaF(alpha)
            pen = QPen(trail_color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            angle_rad = math.radians(i)
            x = math.cos(angle_rad) * radius
            y = math.sin(angle_rad) * radius
            painter.drawLine(QPointF(0, 0), QPointF(x, y))
        painter.restore()
        
        # Sweep arm
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self.sweep_angle - 90)
        arm_color = QColor(self.theme.primary_soft)
        pen = QPen(arm_color)
        pen.setWidthF(1.8)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 0), QPointF(radius, 0))
        painter.restore()
        
        # Blips
        for angle, dist_frac, lifetime in self.blips:
            blip_x = cx + math.cos(math.radians(angle)) * radius * dist_frac
            blip_y = cy + math.sin(math.radians(angle)) * radius * dist_frac
            brightness = lifetime / 50
            blip_color = QColor(self.theme.primary_soft)
            blip_color.setAlphaF(brightness)
            painter.setBrush(QBrush(blip_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(blip_x, blip_y), 2.5, 2.5)
        
        # Center dot
        painter.setBrush(QBrush(primary))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 2.5, 2.5)
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #061410;")
    win.resize(200, 200)
    from Frontend.Themes.scanning_theme import scanning_theme
    w = RadarWidget(theme=scanning_theme)
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec_())