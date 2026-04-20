# =============================================================
#  Frontend/Graphics/StatsBars.py - Live System Stats
#
#  Kya karta:
#    - CPU / RAM / Disk / Battery live bars
#    - Polls psutil every 2 seconds
#    - Smooth bar animation
#    - Network bandwidth (up/down kbps)
#    - Theme-aware
# =============================================================

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame,
)

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False


# =============================================================
#  Single animated stat bar
# =============================================================
class StatBar(QWidget):
    """One horizontal animated bar with label."""
    
    def __init__(self, label: str, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.label_text = label
        
        self.target_value = 0.0   # 0..100
        self.display_value = 0.0
        
        self.setMinimumHeight(28)
        
        # Smooth animation
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(40)
    
    def set_value(self, val: float):
        self.target_value = max(0.0, min(100.0, val))
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()
    
    def _animate(self):
        diff = self.target_value - self.display_value
        if abs(diff) < 0.1:
            self.display_value = self.target_value
        else:
            self.display_value += diff * 0.15
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        primary = QColor(self.theme.primary)
        muted = QColor(self.theme.text_muted)
        warn = QColor(self.theme.warn)
        error = QColor(self.theme.error)
        
        # Label on top-left
        painter.setPen(QPen(muted))
        painter.setFont(self.font())
        painter.drawText(
            0, 0, w, h // 2, Qt.AlignLeft | Qt.AlignVCenter,
            self.label_text,
        )
        
        # Value on top-right
        painter.setPen(QPen(primary))
        painter.drawText(
            0, 0, w, h // 2, Qt.AlignRight | Qt.AlignVCenter,
            f"{int(self.display_value)}%",
        )
        
        # Bar background
        bar_y = h - 8
        bar_h = 5
        bg_color = QColor(self.theme.border)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, bar_y, w, bar_h, 2, 2)
        
        # Fill color based on value
        if self.display_value > 85:
            fill_color = error
        elif self.display_value > 70:
            fill_color = warn
        else:
            fill_color = primary
        
        fill_w = int(w * (self.display_value / 100))
        if fill_w > 0:
            painter.setBrush(QBrush(fill_color))
            painter.drawRoundedRect(0, bar_y, fill_w, bar_h, 2, 2)
        
        painter.end()


# =============================================================
#  Stats panel (bundle of bars + net counters)
# =============================================================
class StatsPanel(QWidget):
    """Full stats panel with 4 bars + network counters."""
    
    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme = theme or neural_theme
        
        self._last_net_sent = 0
        self._last_net_recv = 0
        self._last_net_time = 0
        
        self._build_ui()
        
        # Poll stats
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._update_stats)
        self.poll_timer.start(2000)  # every 2 sec
        self._update_stats()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.cpu_bar = StatBar("CPU", self.theme)
        self.ram_bar = StatBar("RAM", self.theme)
        self.disk_bar = StatBar("DISK", self.theme)
        self.bat_bar = StatBar("BATTERY", self.theme)
        
        layout.addWidget(self.cpu_bar)
        layout.addWidget(self.ram_bar)
        layout.addWidget(self.disk_bar)
        layout.addWidget(self.bat_bar)
        
        # Net row
        net_row = QHBoxLayout()
        net_row.setContentsMargins(0, 4, 0, 0)
        
        self.net_up_label = QLabel("↑ 0 kbps")
        self.net_up_label.setStyleSheet(
            f"color: {self.theme.text_muted}; font-size: 9pt;"
        )
        self.net_down_label = QLabel("↓ 0 kbps")
        self.net_down_label.setStyleSheet(
            f"color: {self.theme.text_muted}; font-size: 9pt;"
        )
        net_row.addWidget(self.net_up_label)
        net_row.addStretch()
        net_row.addWidget(self.net_down_label)
        
        layout.addLayout(net_row)
    
    def set_theme(self, theme: Theme):
        self.theme = theme
        self.cpu_bar.set_theme(theme)
        self.ram_bar.set_theme(theme)
        self.disk_bar.set_theme(theme)
        self.bat_bar.set_theme(theme)
        self.net_up_label.setStyleSheet(
            f"color: {theme.text_muted}; font-size: 9pt;"
        )
        self.net_down_label.setStyleSheet(
            f"color: {theme.text_muted}; font-size: 9pt;"
        )
    
    def _update_stats(self):
        if not PSUTIL_OK:
            return
        
        try:
            import time
            
            # CPU
            self.cpu_bar.set_value(psutil.cpu_percent(interval=None))
            
            # RAM
            self.ram_bar.set_value(psutil.virtual_memory().percent)
            
            # Disk
            self.disk_bar.set_value(psutil.disk_usage("C:\\").percent)
            
            # Battery
            try:
                bat = psutil.sensors_battery()
                if bat:
                    self.bat_bar.set_value(bat.percent)
            except Exception:
                pass
            
            # Network
            net = psutil.net_io_counters()
            now = time.time()
            if self._last_net_time > 0:
                dt = now - self._last_net_time
                sent_delta = net.bytes_sent - self._last_net_sent
                recv_delta = net.bytes_recv - self._last_net_recv
                
                up_kbps = (sent_delta / dt) / 1024
                down_kbps = (recv_delta / dt) / 1024
                
                self.net_up_label.setText(f"↑ {up_kbps:.0f} kbps")
                self.net_down_label.setText(f"↓ {down_kbps:.0f} kbps")
            
            self._last_net_sent = net.bytes_sent
            self._last_net_recv = net.bytes_recv
            self._last_net_time = now
        except Exception:
            pass


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #060B14;")
    win.resize(300, 250)
    w = StatsPanel(theme=neural_theme)
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec_())