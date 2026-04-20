# =============================================================
#  Frontend/Themes/neural_theme.py - Default (cyan) theme
# =============================================================

from Frontend.Themes.base_theme import Theme


class NeuralTheme(Theme):
    def __init__(self):
        super().__init__(
            name="neural",
            
            # Cyan / arc reactor blue
            primary="#00D4FF",
            primary_soft="#4AE2FF",
            accent="#00A8CC",
            
            # Dark background with subtle blue tint
            bg_main="#060B14",
            bg_panel="#0B131F",
            bg_input="#111A28",
            
            # Text
            text_primary="#E0F6FF",
            text_muted="#6B8299",
            text_accent="#00D4FF",
            
            # Borders
            border="#1A2838",
            border_glow="rgba(0, 212, 255, 0.4)",
            
            # State
            success="#00FF8C",
            warn="#FFB020",
            error="#FF3B3B",
            
            transition_ms=400,
        )


neural_theme = NeuralTheme()