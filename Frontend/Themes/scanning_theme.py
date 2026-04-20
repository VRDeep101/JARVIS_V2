# =============================================================
#  Frontend/Themes/scanning_theme.py - Green radar theme
# =============================================================

from Frontend.Themes.base_theme import Theme


class ScanningTheme(Theme):
    def __init__(self):
        super().__init__(
            name="scanning",
            
            # Green radar
            primary="#00FF8C",
            primary_soft="#4AFFAA",
            accent="#00CC6E",
            
            bg_main="#061410",
            bg_panel="#0B1F18",
            bg_input="#112820",
            
            text_primary="#E0FFF0",
            text_muted="#6B9982",
            text_accent="#00FF8C",
            
            border="#1A3828",
            border_glow="rgba(0, 255, 140, 0.4)",
            
            success="#00FF8C",
            warn="#FFB020",
            error="#FF3B3B",
        )


scanning_theme = ScanningTheme()