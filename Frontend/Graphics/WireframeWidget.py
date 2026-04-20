# =============================================================
#  Frontend/Graphics/WireframeWidget.py - 3D Rotating Wireframe
#
#  Kya karta:
#    - Rotating 3D cube/octahedron wireframe
#    - Pure math 2D projection (no opengl)
#    - Aesthetic side panel decoration
# =============================================================

import math
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class WireframeWidget(QWidget):
    """Rotating 3D wireframe shape."""
    
    FPS = 30
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        self.setMinimumSize(120, 120)
        
        self.rotation_x = 0
        self.rotation_y = 0
        
        # Octahedron vertices (nicer than cube)
        self.vertices = [
            (0, 1, 0),    # top
            (0, -1, 0),   # bottom
            (1, 0, 0), (0, 0, 1), (-1, 0, 0), (0, 0, -1),
        ]
        self.edges = [
            (0, 2), (0, 3), (0, 4), (0, 5),  # top to equator
            (1, 2), (1, 3), (1, 4), (1, 5),  # bottom to equator
            (2, 3), (3, 4), (4, 5), (5, 2),  # equator
        ]
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000 // self.FPS)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def _tick(self):
        self.rotation_x += 0.8
        self.rotation_y += 1.2
        self.update()
    
    def _project(self, v, scale):
        """Project 3D point to 2D."""
        x, y, z = v
        
        # Rotate Y
        ry = math.radians(self.rotation_y)
        x2 = x * math.cos(ry) - z * math.sin(ry)
        z2 = x * math.sin(ry) + z * math.cos(ry)
        
        # Rotate X
        rx = math.radians(self.rotation_x)
        y2 = y * math.cos(rx) - z2 * math.sin(rx)
        z3 = y * math.sin(rx) + z2 * math.cos(rx)
        
        return x2 * scale, y2 * scale, z3
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        scale = min(w, h) * 0.35
        
        primary = QColor(self.theme.primary)
        
        # Project all vertices
        projected = [self._project(v, scale) for v in self.vertices]
        
        # Draw edges with depth-based alpha
        for i, j in self.edges:
            x1, y1, z1 = projected[i]
            x2, y2, z2 = projected[j]
            avg_z = (z1 + z2) / 2
            alpha = 0.3 + (avg_z / scale + 1) * 0.35
            
            color = QColor(primary)
            color.setAlphaF(max(0.2, min(1.0, alpha)))
            pen = QPen(color)
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.drawLine(
                QPointF(cx + x1, cy + y1),
                QPointF(cx + x2, cy + y2),
            )
        
        # Draw vertex dots
        for x, y, z in projected:
            brightness = (z / scale + 1) / 2
            color = QColor(self.theme.primary_soft)
            color.setAlphaF(0.3 + brightness * 0.6)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx + x, cy + y), 3, 3)
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(300, 300)
    w = WireframeWidget(theme=neural_theme)
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec_())