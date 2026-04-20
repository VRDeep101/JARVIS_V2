# =============================================================
#  Frontend/Themes/gaming_theme.py - ASUS TUF red/black RGB
# =============================================================

from Frontend.Themes.base_theme import Theme


class GamingTheme(Theme):
    def __init__(self):
        super().__init__(
            name="gaming",
            
            # Aggressive red with green accent (ASUS TUF vibes)
            primary="#FF0044",
            primary_soft="#FF5577",
            accent="#00FF88",
            
            bg_main="#0A0606",
            bg_panel="#140A0A",
            bg_input="#1F1010",
            
            text_primary="#FFEEEE",
            text_muted="#9E7070",
            text_accent="#00FF88",
            
            border="#381414",
            border_glow="rgba(255, 0, 68, 0.5)",
            
            success="#00FF88",
            warn="#FFB020",
            error="#FF0000",
            
            # Snappy transitions
            transition_ms=200,
        )


gaming_theme = GamingTheme()