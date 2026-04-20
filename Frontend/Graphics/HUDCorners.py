# =============================================================
#  Frontend/Graphics/HUDCorners.py - L-Shape Corner Brackets
#
#  Adds HUD-style corner decorations around panels
#  Image 3 style: ┏   ┓
#                  ┗   ┛
# =============================================================

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme


class HUDCorners(QWidget):
    """Overlay widget - draws L-shape brackets in corners."""
    
    def __init__(self, theme: Theme = None, size: int = 20, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        self.corner_size = size
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        s = self.corner_size
        
        primary = QColor(self.theme.primary)
        pen = QPen(primary)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)
        
        # Top-left
        painter.drawLine(0, 0, s, 0)
        painter.drawLine(0, 0, 0, s)
        
        # Top-right
        painter.drawLine(w - s, 0, w, 0)
        painter.drawLine(w, 0, w, s)
        
        # Bottom-left
        painter.drawLine(0, h, s, h)
        painter.drawLine(0, h - s, 0, h)
        
        # Bottom-right
        painter.drawLine(w - s, h, w, h)
        painter.drawLine(w, h - s, w, h)
        
        painter.end()