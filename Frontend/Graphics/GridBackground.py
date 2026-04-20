# =============================================================
#  Frontend/Graphics/GridBackground.py - HUD Grid Overlay
#
#  Blueprint-style grid background (image 3 reference)
#  + Moving scan line
#  + Subtle corner crosshair marks
# =============================================================

from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class GridBackground(QWidget):
    """Grid overlay + moving scan line."""
    
    FPS = 30
    GRID_SIZE = 40
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.scan_y = 0.0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000 // self.FPS)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def _tick(self):
        self.scan_y += 0.002
        if self.scan_y > 1.2:
            self.scan_y = -0.1
        self.update()
    
    def paintEvent(self, event):
        if self.width() == 0 or self.height() == 0:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        primary = QColor(self.theme.primary)
        
        # === Grid lines (very subtle) ===
        grid_color = QColor(primary)
        grid_color.setAlphaF(0.05)
        pen = QPen(grid_color)
        pen.setWidthF(0.5)
        painter.setPen(pen)
        
        # Vertical lines
        for x in range(0, w, self.GRID_SIZE):
            painter.drawLine(x, 0, x, h)
        # Horizontal lines
        for y in range(0, h, self.GRID_SIZE):
            painter.drawLine(0, y, w, y)
        
        # === Major grid (brighter, every 5 cells) ===
        major_color = QColor(primary)
        major_color.setAlphaF(0.10)
        pen = QPen(major_color)
        pen.setWidthF(0.8)
        painter.setPen(pen)
        
        major_gap = self.GRID_SIZE * 5
        for x in range(0, w, major_gap):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, major_gap):
            painter.drawLine(0, y, w, y)
        
        # === Crosshair dots at major intersections ===
        dot_color = QColor(primary)
        dot_color.setAlphaF(0.20)
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.NoPen)
        for x in range(0, w, major_gap):
            for y in range(0, h, major_gap):
                painter.drawEllipse(QPointF(x, y), 1.5, 1.5)
        
        # === Moving scan line (horizontal) ===
        scan_pixel = int(self.scan_y * h)
        if 0 <= scan_pixel <= h:
            scan_grad = QLinearGradient(0, scan_pixel - 30, 0, scan_pixel + 30)
            scan_color = QColor(primary)
            scan_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
            scan_color.setAlphaF(0.08)
            scan_grad.setColorAt(0.5, scan_color)
            scan_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            
            painter.setBrush(QBrush(scan_grad))
            painter.setPen(Qt.NoPen)
            painter.drawRect(0, scan_pixel - 30, w, 60)
            
            # Sharp line in center of scan
            line_color = QColor(primary)
            line_color.setAlphaF(0.15)
            pen = QPen(line_color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawLine(0, scan_pixel, w, scan_pixel)
        
        painter.end()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(800, 600)
    w = GridBackground(theme=neural_theme)
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec_())