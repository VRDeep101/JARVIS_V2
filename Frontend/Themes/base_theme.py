# =============================================================
#  Frontend/Themes/base_theme.py - Theme base class
#
#  Each mode has a theme defining:
#    - Primary color (circle glow, highlights)
#    - Accent color (secondary elements)
#    - Background color
#    - Text colors (primary, muted)
#    - Font styles
#    - Border/panel colors
#
#  Usage:
#    from Frontend.Themes.neural_theme import NeuralTheme
#    t = NeuralTheme()
#    print(t.primary)        -> "#00D4FF"
# =============================================================

from dataclasses import dataclass


@dataclass
class Theme:
    """Base theme dataclass."""
    name: str
    
    # Primary palette
    primary: str             # Main glow color
    primary_soft: str        # Lighter version for fills
    accent: str              # Secondary highlight
    
    # Background
    bg_main: str             # Main window bg
    bg_panel: str            # Panel/card bg
    bg_input: str            # Input field bg
    
    # Text
    text_primary: str        # Main text
    text_muted: str          # Secondary text
    text_accent: str         # Highlighted text
    
    # Borders
    border: str              # Panel borders
    border_glow: str         # Glowing borders (with alpha)
    
    # State colors
    success: str
    warn: str
    error: str
    
    # Typography
    font_main: str = "Segoe UI"
    font_mono: str = "Consolas"
    font_display: str = "Segoe UI"     # for headers
    
    # Animation
    transition_ms: int = 400
    
    def hex_with_alpha(self, hex_color: str, alpha: float) -> str:
        """Convert #RRGGBB + alpha -> rgba(r,g,b,a) for CSS."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        a = max(0.0, min(1.0, alpha))
        return f"rgba({r}, {g}, {b}, {a})"
    
    # =========================================================
    #  Common QSS stylesheet generator
    # =========================================================
    def build_qss(self) -> str:
        """Generate full QSS stylesheet for the theme."""
        return f"""
        /* ===== GLOBAL ===== */
        QWidget {{
            background-color: {self.bg_main};
            color: {self.text_primary};
            font-family: "{self.font_main}";
            font-size: 10pt;
        }}
        
        QMainWindow {{
            background-color: {self.bg_main};
        }}
        
        /* ===== PANELS ===== */
        QFrame#panel {{
            background-color: {self.bg_panel};
            border: 1px solid {self.border};
            border-radius: 8px;
        }}
        
        QFrame#panel_glow {{
            background-color: {self.bg_panel};
            border: 1px solid {self.hex_with_alpha(self.primary, 0.6)};
            border-radius: 8px;
        }}
        
        /* ===== LABELS ===== */
        QLabel {{
            background-color: transparent;
            color: {self.text_primary};
        }}
        
        QLabel#title {{
            color: {self.primary};
            font-family: "{self.font_display}";
            font-size: 14pt;
            font-weight: bold;
            letter-spacing: 2px;
        }}
        
        QLabel#status {{
            color: {self.primary};
            font-family: "{self.font_display}";
            font-size: 11pt;
            letter-spacing: 1px;
        }}
        
        QLabel#muted {{
            color: {self.text_muted};
            font-size: 9pt;
        }}
        
        QLabel#mode_badge {{
            color: {self.primary};
            background-color: {self.hex_with_alpha(self.primary, 0.15)};
            border: 1px solid {self.hex_with_alpha(self.primary, 0.5)};
            border-radius: 4px;
            padding: 3px 10px;
            font-family: "{self.font_display}";
            font-size: 9pt;
            font-weight: bold;
            letter-spacing: 2px;
        }}
        
        /* ===== BUTTONS ===== */
        QPushButton {{
            background-color: transparent;
            color: {self.primary};
            border: 1px solid {self.hex_with_alpha(self.primary, 0.6)};
            border-radius: 4px;
            padding: 6px 14px;
            font-family: "{self.font_display}";
            font-size: 9pt;
            letter-spacing: 1px;
        }}
        QPushButton:hover {{
            background-color: {self.hex_with_alpha(self.primary, 0.12)};
            border: 1px solid {self.primary};
        }}
        QPushButton:pressed {{
            background-color: {self.hex_with_alpha(self.primary, 0.25)};
        }}
        
        /* ===== INPUTS ===== */
        QLineEdit, QTextEdit {{
            background-color: {self.bg_input};
            color: {self.text_primary};
            border: 1px solid {self.border};
            border-radius: 4px;
            padding: 6px;
            font-family: "{self.font_mono}";
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {self.primary};
        }}
        
        /* ===== SCROLLBARS ===== */
        QScrollBar:vertical {{
            background: {self.bg_panel};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {self.hex_with_alpha(self.primary, 0.4)};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {self.primary};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0;
        }}
        
        QScrollBar:horizontal {{
            background: {self.bg_panel};
            height: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {self.hex_with_alpha(self.primary, 0.4)};
            border-radius: 4px;
            min-width: 20px;
        }}
        
        /* ===== PROGRESS / SLIDERS ===== */
        QProgressBar {{
            background-color: {self.bg_input};
            border: 1px solid {self.border};
            border-radius: 3px;
            text-align: center;
            color: {self.text_primary};
            height: 6px;
        }}
        QProgressBar::chunk {{
            background-color: {self.primary};
            border-radius: 2px;
        }}
        """