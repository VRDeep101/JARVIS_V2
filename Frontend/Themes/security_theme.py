# =============================================================
#  Frontend/Themes/security_theme.py - Red alert theme
# =============================================================

from Frontend.Themes.base_theme import Theme


class SecurityTheme(Theme):
    def __init__(self):
        super().__init__(
            name="security",
            
            # Red alert
            primary="#FF3B3B",
            primary_soft="#FF6B6B",
            accent="#CC0000",
            
            bg_main="#100606",
            bg_panel="#1A0B0B",
            bg_input="#231111",
            
            text_primary="#FFE0E0",
            text_muted="#9E7272",
            text_accent="#FF3B3B",
            
            border="#3A1A1A",
            border_glow="rgba(255, 59, 59, 0.4)",
            
            success="#00FF8C",
            warn="#FFB020",
            error="#FF0000",
        )


security_theme = SecurityTheme()