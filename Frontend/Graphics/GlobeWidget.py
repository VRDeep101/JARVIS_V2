# =============================================================
#  Frontend/Graphics/GlobeWidget.py - WITH CONTINENTS
#
#  Now includes actual continent outlines (simplified dot map).
#  Rotates like real earth with visible landmasses.
# =============================================================

import math
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


# =============================================================
#  Continent dots - simplified world map (lat, lon) coordinates
#  Covers major landmasses with dense dots
# =============================================================
CONTINENT_DOTS = []

def _build_continent_dots():
    """Build a dotted representation of world continents."""
    dots = []
    
    # Helper: add rectangular region filled with dots
    def fill_region(lat1, lat2, lon1, lon2, density=8):
        step_lat = (lat2 - lat1) / density
        step_lon = (lon2 - lon1) / density
        for i in range(density + 1):
            for j in range(density + 1):
                lat = lat1 + i * step_lat
                lon = lon1 + j * step_lon
                dots.append((lat, lon))
    
    # === North America ===
    fill_region(30, 70, -130, -100, 10)   # main block
    fill_region(25, 50, -100, -75, 8)     # eastern USA
    fill_region(50, 70, -95, -60, 6)      # canada east
    fill_region(60, 80, -150, -90, 5)     # northern canada/alaska
    fill_region(15, 30, -110, -85, 5)     # mexico
    
    # === South America ===
    fill_region(-10, 10, -80, -50, 6)     # amazon
    fill_region(-30, -10, -75, -45, 8)    # brazil
    fill_region(-55, -30, -75, -60, 6)    # southern
    fill_region(0, 12, -80, -60, 4)       # north SA
    
    # === Europe ===
    fill_region(40, 60, -10, 30, 8)       # main europe
    fill_region(55, 70, 10, 40, 6)        # scandinavia
    fill_region(35, 45, -5, 25, 5)        # mediterranean north
    
    # === Africa ===
    fill_region(-10, 15, 0, 35, 10)       # central africa
    fill_region(-35, -10, 15, 35, 8)      # south africa
    fill_region(15, 30, -15, 35, 10)      # sahara/north africa
    fill_region(-10, 5, 10, 40, 6)        # congo
    
    # === Asia ===
    fill_region(20, 55, 60, 140, 15)      # main asia
    fill_region(45, 70, 60, 180, 12)      # siberia
    fill_region(5, 25, 70, 100, 6)        # india
    fill_region(20, 40, 100, 145, 8)      # china/japan area
    fill_region(-10, 10, 95, 140, 6)      # indonesia/SE asia
    
    # === Australia ===
    fill_region(-40, -10, 112, 155, 8)
    
    return dots

CONTINENT_DOTS = _build_continent_dots()


class GlobeWidget(QWidget):
    """Rotating 3D globe with continent outlines."""
    
    FPS = 30
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        self.setMinimumSize(160, 160)
        
        self.rotation = 0.0
        self.tilt = 23.5
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000 // self.FPS)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def _tick(self):
        self.rotation += 0.5
        if self.rotation >= 360:
            self.rotation -= 360
        self.update()
    
    def _project(self, lat, lon, radius):
        """Project 3D sphere point to 2D."""
        lat_r = math.radians(lat)
        lon_r = math.radians(lon + self.rotation)
        
        x = radius * math.cos(lat_r) * math.sin(lon_r)
        y = radius * math.sin(lat_r)
        z = radius * math.cos(lat_r) * math.cos(lon_r)
        
        tilt_r = math.radians(self.tilt)
        y2 = y * math.cos(tilt_r) - z * math.sin(tilt_r)
        z2 = y * math.sin(tilt_r) + z * math.cos(tilt_r)
        
        return x, y2, z2
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        radius = min(w, h) * 0.40
        
        primary = QColor(self.theme.primary)
        primary_soft = QColor(self.theme.primary_soft)
        
        # Outer soft ring
        ring_color = QColor(primary)
        ring_color.setAlphaF(0.2)
        pen = QPen(ring_color)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius * 1.15, radius * 1.15)
        
        # Globe outline
        outline_color = QColor(primary)
        outline_color.setAlphaF(0.5)
        pen = QPen(outline_color)
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        
        # === Latitude grid (thin) ===
        for lat in [-60, -30, 30, 60]:
            points = []
            for lon in range(0, 361, 6):
                x, y, z = self._project(lat, lon, radius)
                if z >= -5:
                    alpha = (z + radius) / (2 * radius)
                    points.append((cx + x, cy - y, alpha))
            
            for i in range(len(points) - 1):
                x1, y1, a1 = points[i]
                x2, y2, a2 = points[i + 1]
                avg = (a1 + a2) / 2
                color = QColor(primary)
                color.setAlphaF(0.15 + avg * 0.2)
                pen = QPen(color)
                pen.setWidthF(0.6)
                painter.setPen(pen)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        
        # === Meridians (thin) ===
        for lon in range(0, 180, 30):
            points = []
            for lat in range(-90, 91, 8):
                x, y, z = self._project(lat, lon, radius)
                if z >= -5:
                    alpha = (z + radius) / (2 * radius)
                    points.append((cx + x, cy - y, alpha))
            
            for i in range(len(points) - 1):
                x1, y1, a1 = points[i]
                x2, y2, a2 = points[i + 1]
                avg = (a1 + a2) / 2
                color = QColor(primary)
                color.setAlphaF(0.12 + avg * 0.15)
                pen = QPen(color)
                pen.setWidthF(0.6)
                painter.setPen(pen)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        
        # === Equator (brighter) ===
        points = []
        for lon in range(0, 361, 4):
            x, y, z = self._project(0, lon, radius)
            if z >= -5:
                points.append((cx + x, cy - y, z))
        
        for i in range(len(points) - 1):
            x1, y1, z1 = points[i]
            x2, y2, z2 = points[i + 1]
            alpha = max(0.3, (z1 + radius) / (2 * radius))
            color = QColor(primary_soft)
            color.setAlphaF(alpha * 0.6)
            pen = QPen(color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        
        # =========================================================
        #  CONTINENTS - dotted landmasses
        # =========================================================
        painter.setPen(Qt.NoPen)
        
        for lat, lon in CONTINENT_DOTS:
            x, y, z = self._project(lat, lon, radius)
            if z >= 0:  # only front-facing
                # Brightness based on how facing us it is
                brightness = (z / radius)  # 0 to 1
                
                color = QColor(primary_soft)
                color.setAlphaF(0.3 + brightness * 0.6)
                
                painter.setBrush(QBrush(color))
                # Slightly larger dots for closer points (perspective)
                dot_size = 1.2 + brightness * 0.8
                painter.drawEllipse(QPointF(cx + x, cy - y), dot_size, dot_size)
        
        # =========================================================
        #  City highlights (brighter dots)
        # =========================================================
        cities = [
            (19.0, 73.0),    # Pune (home!)
            (28.6, 77.2),    # Delhi
            (40.7, -74.0),   # New York
            (51.5, -0.1),    # London
            (35.7, 139.7),   # Tokyo
            (-33.9, 151.2),  # Sydney
        ]
        for lat, lon in cities:
            x, y, z = self._project(lat, lon, radius)
            if z >= 0:
                brightness = (z / radius)
                # Pulsing effect for home city (Pune)
                if lat == 19.0 and lon == 73.0:
                    import math
                    pulse = (math.sin(self.rotation * 0.2) + 1) / 2
                    color = QColor(self.theme.warn)  # gold/yellow
                    color.setAlphaF(0.7 + pulse * 0.3)
                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(
                        QPointF(cx + x, cy - y), 3.5, 3.5
                    )
                else:
                    color = QColor(255, 255, 255)
                    color.setAlphaF(0.5 + brightness * 0.4)
                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(
                        QPointF(cx + x, cy - y), 2.5, 2.5
                    )
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(400, 400)
    w = GlobeWidget(theme=neural_theme)
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec_())