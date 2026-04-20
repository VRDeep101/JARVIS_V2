# =============================================================
#  Backend/Core/ModeManager.py - 5-Mode System Manager
#
#  Kya karta:
#    - 5 modes manage karta (Neural/Security/Scanning/Companion/Gaming)
#    - Offline auto-detect karta (not a chosen mode)
#    - Mode switching with callbacks (GUI theme, sounds, voice)
#    - Companion vault access control (strict isolation)
#    - Current mode state singleton
#
#  Modes:
#    NEURAL    - Default, regular Jarvis
#    SECURITY  - Phishing + clipboard + threats
#    SCANNING  - WiFi/device/system scans
#    COMPANION - Emotional care, password-protected (1406)
#    GAMING    - Performance mode for ASUS TUF A15
#    OFFLINE   - Auto-triggered when net down
#
#  Usage:
#    from Backend.Core.ModeManager import mode_manager, Mode
#    mode_manager.current_mode       -> Mode.NEURAL
#    mode_manager.switch(Mode.GAMING)
#    mode_manager.can_access_vault() -> True/False
#    mode_manager.register_callback(fn)
# =============================================================

import time
import threading
from enum import Enum
from typing import Callable, List, Optional
from datetime import datetime

from Backend.Utils.Logger import get_logger
from Backend.Utils.InternetCheck import net

log = get_logger("ModeManager")

# -- Mode Enum ------------------------------------------------
class Mode(Enum):
    NEURAL    = "neural"
    SECURITY  = "security"
    SCANNING  = "scanning"
    COMPANION = "companion"
    GAMING    = "gaming"
    OFFLINE   = "offline"

# -- Mode Metadata ---------------------------------------------
MODE_INFO = {
    Mode.NEURAL: {
        "name": "Neural",
        "display": "NEURAL MODE",
        "color": "#00D4FF",
        "voice_announce": "Neural mode active, Sir. At your service.",
        "description": "Regular Jarvis - chat, automation, AI routing",
        "password_required": False,
        "icon": "brain",
    },
    Mode.SECURITY: {
        "name": "Security",
        "display": "SECURITY MODE",
        "color": "#FF3B3B",
        "voice_announce": "Security mode activated. Actively monitoring for threats, Sir.",
        "description": "Phishing detection, clipboard monitor, breach check",
        "password_required": False,
        "icon": "shield",
    },
    Mode.SCANNING: {
        "name": "Scanning",
        "display": "SCANNING MODE",
        "color": "#00FF8C",
        "voice_announce": "Scanning mode activated. What should I scan, Sir - WiFi, devices, system, or network?",
        "description": "WiFi, Bluetooth, device, system, network scans",
        "password_required": False,
        "icon": "radar",
    },
    Mode.COMPANION: {
        "name": "Companion",
        "display": "COMPANION MODE",
        "color": "#B08CE5",
        "voice_announce": "Welcome back, Deep. I'm here. Take your time.",
        "description": "Emotional care, memory lane, private vault access",
        "password_required": True,
        "icon": "bond",
    },
    Mode.GAMING: {
        "name": "Gaming",
        "display": "GAMING MODE",
        "color": "#FF0044",
        "voice_announce": "Gaming mode activated, Sir. Maximum performance engaged.",
        "description": "Performance optimization + ASUS TUF monitoring",
        "password_required": False,
        "icon": "gamepad",
    },
    Mode.OFFLINE: {
        "name": "Offline",
        "display": "OFFLINE MODE",
        "color": "#8A8F9A",
        "voice_announce": "We're offline, Sir. Running on local capabilities.",
        "description": "Auto-triggered when no internet",
        "password_required": False,
        "icon": "cloud-off",
    },
}

# -- Trigger phrases (voice commands for mode switching) -------
MODE_TRIGGERS = {
    Mode.NEURAL: [
        "neural mode", "back to normal", "normal mode", "regular mode",
        "default mode", "exit companion", "exit gaming", "exit security",
        "exit scanning", "back to neural",
    ],
    Mode.SECURITY: [
        "security mode", "activate security", "security on",
        "enable security", "protection mode",
    ],
    Mode.SCANNING: [
        "scanning mode", "scan mode", "activate scanning",
        "start scanning", "enable scanning",
    ],
    Mode.COMPANION: [
        "companion mode", "be my companion", "companion",
        "personal mode", "intimate mode",
    ],
    Mode.GAMING: [
        "gaming mode", "game mode", "gaming on",
        "boost performance", "gamer mode",
    ],
}

# -- State singleton -------------------------------------------
class _ModeState:
    """Internal state holder (private)."""
    current: Mode = Mode.NEURAL
    previous: Optional[Mode] = None
    entered_at: float = 0.0
    was_offline: bool = False
    callbacks: List[Callable[[Mode, Mode], None]] = []
    _lock = threading.Lock()

# -- Main class ------------------------------------------------
class ModeManager:
    """
    Centralized 5-mode system.
    All mode switches go through this.
    """
    
    def __init__(self):
        _ModeState.entered_at = time.time()
        # Start net monitor for auto-offline detection
        try:
            net.start_monitor(interval=10)
            net.on_state_change(self._on_net_change)
        except Exception as e:
            log.warn(f"Net monitor start failed: {e}")
    
    # -- Properties -------------------------------------------
    @property
    def current_mode(self) -> Mode:
        return _ModeState.current
    
    @property
    def current_info(self) -> dict:
        return MODE_INFO[_ModeState.current]
    
    @property
    def previous_mode(self) -> Optional[Mode]:
        return _ModeState.previous
    
    @property
    def time_in_mode(self) -> float:
        """Seconds since current mode activated."""
        return time.time() - _ModeState.entered_at
    
    def is_mode(self, mode: Mode) -> bool:
        return _ModeState.current == mode
    
    def is_companion(self) -> bool:
        return _ModeState.current == Mode.COMPANION
    
    def is_offline(self) -> bool:
        return _ModeState.current == Mode.OFFLINE
    
    # -- Access control ---------------------------------------
    def can_access_vault(self) -> bool:
        """
        Companion vault access - STRICT RULE.
        Only Companion mode can read/write companion_vault.json.
        """
        return _ModeState.current == Mode.COMPANION
    
    def can_access_normal_memory(self) -> bool:
        """Every mode can access normal long-term memory."""
        return True
    
    # -- Mode switching ---------------------------------------
    def switch(self, new_mode: Mode, silent: bool = False) -> bool:
        """
        Switch to a new mode.
        Returns True on success, False if blocked.
        
        Note: Companion mode password check must be done BEFORE calling this.
        """
        with _ModeState._lock:
            if new_mode == _ModeState.current:
                log.debug(f"Already in {new_mode.value} mode")
                return True
            
            old = _ModeState.current
            _ModeState.previous = old
            _ModeState.current = new_mode
            _ModeState.entered_at = time.time()
            
            log.info(f"Mode: {old.value} -> {new_mode.value}")
            
            # Fire callbacks
            for cb in list(_ModeState.callbacks):
                try:
                    cb(old, new_mode)
                except Exception as e:
                    log.error(f"Mode callback error: {e}")
            
            return True
    
    def switch_back(self) -> bool:
        """Go back to previous mode (if any)."""
        if _ModeState.previous:
            return self.switch(_ModeState.previous)
        return self.switch(Mode.NEURAL)
    
    def detect_mode_from_query(self, query: str) -> Optional[Mode]:
        """
        Check if user query is requesting a mode switch.
        Returns target Mode or None.
        """
        q = query.lower().strip()
        for mode, triggers in MODE_TRIGGERS.items():
            for phrase in triggers:
                if phrase in q:
                    return mode
        return None
    
    # -- Offline auto-switch ----------------------------------
    def _on_net_change(self, online: bool):
        """Callback: net state changed."""
        if not online and _ModeState.current != Mode.OFFLINE:
            # Net went down - save current mode and switch to offline
            log.warn("Internet lost - switching to OFFLINE mode")
            _ModeState.was_offline = True
            # Save current mode for restoration
            prev = _ModeState.current
            self.switch(Mode.OFFLINE)
            _ModeState.previous = prev
        
        elif online and _ModeState.current == Mode.OFFLINE:
            # Net came back - restore previous mode
            log.info("Internet restored - exiting OFFLINE")
            _ModeState.was_offline = False
            restore = _ModeState.previous or Mode.NEURAL
            self.switch(restore)
    
    # -- Callbacks --------------------------------------------
    def register_callback(self, callback: Callable[[Mode, Mode], None]):
        """
        Register fn called on mode switch.
        callback(old_mode: Mode, new_mode: Mode)
        """
        with _ModeState._lock:
            if callback not in _ModeState.callbacks:
                _ModeState.callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        with _ModeState._lock:
            if callback in _ModeState.callbacks:
                _ModeState.callbacks.remove(callback)
    
    # -- Info helpers -----------------------------------------
    def get_voice_announcement(self) -> str:
        """Voice line to speak when entering current mode."""
        return MODE_INFO[_ModeState.current]["voice_announce"]
    
    def get_current_color(self) -> str:
        """Hex color for current mode (for GUI theme)."""
        return MODE_INFO[_ModeState.current]["color"]
    
    def get_current_display_name(self) -> str:
        """e.g. 'NEURAL MODE' for status bar."""
        return MODE_INFO[_ModeState.current]["display"]
    
    def list_all_modes(self) -> List[dict]:
        """All modes with metadata (for UI/listing)."""
        return [
            {"mode": m, **info}
            for m, info in MODE_INFO.items()
        ]

# -- Singleton -------------------------------------------------
mode_manager = ModeManager()

# -- Test block ------------------------------------------------
if __name__ == "__main__":
    print("\n--- ModeManager Test ---\n")
    
    print(f"Current mode   : {mode_manager.current_mode.value}")
    print(f"Display name   : {mode_manager.get_current_display_name()}")
    print(f"Color          : {mode_manager.get_current_color()}")
    print(f"Can access vault: {mode_manager.can_access_vault()}")
    
    # Test callback
    def on_switch(old, new):
        print(f"  [CALLBACK] {old.value} -> {new.value}")
    
    mode_manager.register_callback(on_switch)
    
    # Test trigger detection
    print("\n-- Trigger detection --")
    test_queries = [
        "Jarvis, switch to gaming mode",
        "activate security mode please",
        "back to neural",
        "what's the weather",   # should return None
    ]
    for q in test_queries:
        detected = mode_manager.detect_mode_from_query(q)
        print(f"  '{q[:40]}' -> {detected.value if detected else 'None'}")
    
    # Test switches
    print("\n-- Switching modes --")
    mode_manager.switch(Mode.SECURITY)
    print(f"  Now: {mode_manager.current_mode.value} | Color: {mode_manager.get_current_color()}")
    print(f"  Vault access: {mode_manager.can_access_vault()}")
    
    mode_manager.switch(Mode.COMPANION)
    print(f"  Now: {mode_manager.current_mode.value} | Color: {mode_manager.get_current_color()}")
    print(f"  Vault access: {mode_manager.can_access_vault()}  <-- should be True")
    print(f"  Voice line: {mode_manager.get_voice_announcement()}")
    
    mode_manager.switch_back()
    print(f"  Back to: {mode_manager.current_mode.value}")
    
    mode_manager.switch(Mode.NEURAL)
    print(f"  Final: {mode_manager.current_mode.value}")
    
    # List all
    print("\n-- All modes --")
    for m_info in mode_manager.list_all_modes():
        print(f"  {m_info['display']:18} | {m_info['color']} | pwd={m_info['password_required']}")
    
    print("\n[OK] ModeManager test complete\n")