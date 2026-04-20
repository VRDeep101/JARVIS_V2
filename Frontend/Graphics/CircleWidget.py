# =============================================================
#  Frontend/Graphics/CircleWidget.py - REDESIGNED
#  Multi-ring HUD circle - image 3 reference style
# =============================================================

import math
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
)
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class CircleWidget(QWidget):
    """Multi-ring animated HUD circle - image 3 style."""
    
    FPS = 60
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        
        self.setMinimumSize(320, 320)
        
        self.tick = 0
        self.pulsing = False
        self.pulse_intensity = 0.0
        self.listening = False
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_tick)
        self.timer.start(1000 // self.FPS)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def set_pulsing(self, active: bool):
        self.pulsing = active
    
    def set_listening(self, active: bool):
        self.listening = active
    
    def _update_tick(self):
        self.tick += 1
        target = 1.0 if self.pulsing else 0.0
        diff = target - self.pulse_intensity
        self.pulse_intensity += diff * 0.08
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        
        # Reduced size — fits in box (0.7 instead of 0.9)
        size = min(w, h) * 0.72
        
        primary = QColor(self.theme.primary)
        primary_soft = QColor(self.theme.primary_soft)
        
        breathe = 1.0 + math.sin(self.tick * 0.04) * 0.015
        pulse_boost = self.pulse_intensity * (
            0.04 + 0.06 * abs(math.sin(self.tick * 0.25))
        )
        total_scale = breathe + pulse_boost
        base_radius = size / 2 * total_scale
        
        # =========================================================
        #  LAYER 1: Outer soft halo
        # =========================================================
        glow_color = QColor(primary)
        glow_color.setAlphaF(0.06 + self.pulse_intensity * 0.10)
        halo_radius = base_radius * 1.20
        gradient = QRadialGradient(cx, cy, halo_radius)
        gradient.setColorAt(0.5, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.88, glow_color)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), halo_radius, halo_radius)
        
        # =========================================================
        #  LAYER 2: Outermost ring - thick arc segments (rotating)
        # =========================================================
        outer_r = base_radius * 1.0
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.tick * 0.25)
        
        pen = QPen(primary)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        # 6 arc segments with gaps
        for i in range(6):
            start = i * 60 + 5
            span = 50
            painter.drawArc(
                QRectF(-outer_r, -outer_r, outer_r * 2, outer_r * 2),
                int(start * 16), int(span * 16)
            )
        painter.restore()
        
        # =========================================================
        #  LAYER 3: Tick marks ring (fine detail)
        # =========================================================
        tick_r = base_radius * 0.92
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self.tick * 0.4)
        
        pen = QPen(primary_soft)
        pen.setWidthF(1.2)
        painter.setPen(pen)
        
        for i in range(36):
            angle = i * 10
            painter.save()
            painter.rotate(angle)
            length = 10 if (i % 3 == 0) else 5
            painter.drawLine(
                QPointF(tick_r, 0),
                QPointF(tick_r - length, 0)
            )
            painter.restore()
        painter.restore()
        
        # =========================================================
        #  LAYER 4: Middle thick ring - solid
        # =========================================================
        mid_r = base_radius * 0.75
        pen = QPen(primary)
        pen.setWidthF(2.5)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), mid_r, mid_r)
        
        # =========================================================
        #  LAYER 5: Broken ring with dashes (rotating opposite)
        # =========================================================
        dash_r = base_radius * 0.63
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.tick * 0.8)
        
        pen = QPen(primary_soft)
        pen.setWidthF(1.8)
        pen.setStyle(Qt.DashLine)
        pen.setDashPattern([3, 2])
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(0, 0), dash_r, dash_r)
        painter.restore()
        
        # =========================================================
        #  LAYER 6: Inner arc segments (rotating - fast)
        # =========================================================
        inner_arc_r = base_radius * 0.50
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self.tick * 1.5)
        
        pen = QPen(primary)
        pen.setWidthF(2.5)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        # 3 arc segments
        for i in range(3):
            start = i * 120 + 15
            span = 90
            painter.drawArc(
                QRectF(-inner_arc_r, -inner_arc_r, inner_arc_r * 2, inner_arc_r * 2),
                int(start * 16), int(span * 16)
            )
        painter.restore()
        
        # =========================================================
        #  LAYER 7: Inner circle (thin, fast rotating dashes)
        # =========================================================
        fast_r = base_radius * 0.38
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.tick * 2.2)
        
        pen = QPen(primary_soft)
        pen.setWidthF(1.0)
        pen.setStyle(Qt.DashLine)
        pen.setDashPattern([2, 2])
        painter.setPen(pen)
        painter.drawEllipse(QPointF(0, 0), fast_r, fast_r)
        painter.restore()
        
        # =========================================================
        #  LAYER 8: BRIGHT WHITE CORE (image 3 signature)
        # =========================================================
        core_r = base_radius * 0.22 * (1.0 + self.pulse_intensity * 0.2)
        
        # Outer glow
        glow_gradient = QRadialGradient(cx, cy, core_r * 2)
        primary_glow = QColor(primary_soft)
        primary_glow.setAlphaF(0.5)
        glow_gradient.setColorAt(0.0, primary_glow)
        glow_gradient.setColorAt(0.4, QColor(primary))
        glow_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_r * 2, core_r * 2)
        
        # Solid bright core (white-ish gradient)
        core_gradient = QRadialGradient(cx, cy, core_r)
        core_gradient.setColorAt(0.0, QColor(255, 255, 255, 255))
        core_gradient.setColorAt(0.5, QColor(255, 255, 255, 200))
        core_gradient.setColorAt(0.8, primary_soft)
        core_gradient.setColorAt(1.0, primary)
        painter.setBrush(QBrush(core_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)
        
        # Ultra-bright center dot
        dot_r = core_r * 0.4
        painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), dot_r, dot_r)
        
        # =========================================================
        #  LAYER 9: Listening pulse dots
        # =========================================================
        if self.listening:
            dot_ring_r = base_radius * 1.08
            painter.setPen(Qt.NoPen)
            for i in range(6):
                angle = math.radians(self.tick * 1.5 + i * 60)
                dx = cx + math.cos(angle) * dot_ring_r
                dy = cy + math.sin(angle) * dot_ring_r
                alpha = (math.sin(self.tick * 0.2 + i * 1.0) + 1) / 2
                dot_color = QColor(primary_soft)
                dot_color.setAlphaF(0.3 + alpha * 0.6)
                painter.setBrush(QBrush(dot_color))
                painter.drawEllipse(QPointF(dx, dy), 4, 4)
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(600, 700)
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    circle = CircleWidget(theme=neural_theme)
    layout.addWidget(circle)
    
    btn = QPushButton("Toggle Pulse")
    btn.setStyleSheet("color: #00D4FF; background: transparent; border: 1px solid #00D4FF; padding: 8px;")
    state = [False]
    def toggle():
        state[0] = not state[0]
        circle.set_pulsing(state[0])
    btn.clicked.connect(toggle)
    layout.addWidget(btn)
    
    win.setCentralWidget(central)
    win.show()
    sys.exit(app.exec_())