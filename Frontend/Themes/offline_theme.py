# =============================================================
#  Frontend/Themes/offline_theme.py - Desaturated gray
# =============================================================

from Frontend.Themes.base_theme import Theme


class OfflineTheme(Theme):
    def __init__(self):
        super().__init__(
            name="offline",
            
            # Muted gray
            primary="#8A8F9A",
            primary_soft="#B0B5BF",
            accent="#6B707A",
            
            bg_main="#0C0E11",
            bg_panel="#141619",
            bg_input="#1A1D21",
            
            text_primary="#C0C5CC",
            text_muted="#6B707A",
            text_accent="#B0B5BF",
            
            border="#252830",
            border_glow="rgba(138, 143, 154, 0.3)",
            
            success="#8AC89E",
            warn="#C89E6B",
            error="#C87070",
        )


offline_theme = OfflineTheme()