# =============================================================
#  Backend/Modes/OfflineMode.py - Offline Fallback
#
#  Kya karta:
#    - Auto-triggered by ModeManager when net down
#    - Preserves previous mode for restoration
#    - Disables: web search, AI routing, image gen, Spotify web
#    - Keeps active: local automation, system controls, memory, EQ
#    - Announces limitations + available capabilities
#
#  Usage:
#    Auto: ModeManager handles net state changes
#    Manual: offline_mode.enter() / .exit()
# =============================================================

from typing import Callable, Optional, List

from Backend.Utils.Logger import get_logger
from Backend.Core.ModeManager import mode_manager, Mode
from Backend.Utils.InternetCheck import net

log = get_logger("OfflineMode")

# Capabilities that work/don't work in offline
AVAILABLE_OFFLINE = [
    "open/close apps",
    "volume and brightness control",
    "screenshots",
    "screen recording",
    "lock screen",
    "system stats",
    "memory recall",
    "time/date queries",
]

UNAVAILABLE_OFFLINE = [
    "web search",
    "AI chat (Groq/Gemini)",
    "image generation",
    "weather/news",
    "WhatsApp web",
    "AI web automation",
]

class OfflineMode:
    """Offline capability handler."""
    
    def __init__(self):
        self.active = False
        self.on_speak: Optional[Callable] = None
    
    def enter(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        self.active = True
        self.on_speak = on_speak
        
        announce = mode_manager.current_info["voice_announce"]
        log.info("Offline mode entered (net down)")
        
        if on_speak:
            on_speak(announce)
        
        return announce
    
    def exit(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        self.active = False
        msg = "Back online, Sir. Full capabilities restored."
        log.info("Offline mode exited (net restored)")
        if on_speak:
            on_speak(msg)
        return msg
    
    def is_active(self) -> bool:
        return self.active and mode_manager.current_mode == Mode.OFFLINE
    
    def get_available(self) -> List[str]:
        return AVAILABLE_OFFLINE
    
    def get_unavailable(self) -> List[str]:
        return UNAVAILABLE_OFFLINE
    
    def can_handle(self, action: str) -> bool:
        """Check if an action can run offline."""
        offline_actions = {
            "open", "close", "system", "mode_switch", "exit",
            "save_data", "clear_data", "general",
        }
        # "general" can work offline if it doesn't require LLM
        # but LLM needs net, so should route to "limited" response
        return action in offline_actions and action != "general"

# Singleton
offline_mode = OfflineMode()

if __name__ == "__main__":
    print("\n--- OfflineMode Test ---\n")
    
    print(f"Net status: {'ONLINE' if net.is_online() else 'OFFLINE'}")
    print(f"\nAvailable offline:")
    for a in offline_mode.get_available():
        print(f"  + {a}")
    print(f"\nUnavailable offline:")
    for a in offline_mode.get_unavailable():
        print(f"  - {a}")
    
    print("\n[OK] OfflineMode test complete\n")