# =============================================================
#  Frontend/Themes/__init__.py - Theme registry
# =============================================================

from Frontend.Themes.base_theme import Theme
from Frontend.Themes.neural_theme import neural_theme, NeuralTheme
from Frontend.Themes.security_theme import security_theme, SecurityTheme
from Frontend.Themes.scanning_theme import scanning_theme, ScanningTheme
from Frontend.Themes.companion_theme import companion_theme, CompanionTheme
from Frontend.Themes.gaming_theme import gaming_theme, GamingTheme
from Frontend.Themes.offline_theme import offline_theme, OfflineTheme

from Backend.Core.ModeManager import Mode

# Map mode enum -> theme
THEME_MAP = {
    Mode.NEURAL:    neural_theme,
    Mode.SECURITY:  security_theme,
    Mode.SCANNING:  scanning_theme,
    Mode.COMPANION: companion_theme,
    Mode.GAMING:    gaming_theme,
    Mode.OFFLINE:   offline_theme,
}


def theme_for_mode(mode: Mode) -> Theme:
    """Get theme object for a mode."""
    return THEME_MAP.get(mode, neural_theme)


__all__ = [
    "Theme",
    "NeuralTheme", "SecurityTheme", "ScanningTheme",
    "CompanionTheme", "GamingTheme", "OfflineTheme",
    "neural_theme", "security_theme", "scanning_theme",
    "companion_theme", "gaming_theme", "offline_theme",
    "theme_for_mode", "THEME_MAP",
]