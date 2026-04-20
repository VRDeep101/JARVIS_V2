# =============================================================
#  Frontend/Themes/companion_theme.py - Soft lavender/gold
# =============================================================

from Frontend.Themes.base_theme import Theme


class CompanionTheme(Theme):
    def __init__(self):
        super().__init__(
            name="companion",
            
            # Soft lavender with warm gold accent
            primary="#B08CE5",
            primary_soft="#D1B8F0",
            accent="#D4A373",        # warm gold
            
            bg_main="#130B1F",
            bg_panel="#1D1530",
            bg_input="#241A38",
            
            text_primary="#F0E5FF",
            text_muted="#9985B0",
            text_accent="#D4A373",
            
            border="#2D2245",
            border_glow="rgba(176, 140, 229, 0.4)",
            
            success="#B8E0C8",
            warn="#FFB570",
            error="#FF8B8B",
            
            # Slower, calmer transitions
            transition_ms=700,
        )


companion_theme = CompanionTheme()