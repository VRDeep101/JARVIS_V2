# =============================================================
#  Backend/Modes/NeuralMode.py - Default Mode Handler
#
#  Kya karta:
#    - Default Jarvis behavior - all standard features active
#    - Entry/exit handlers (announce, cleanup)
#    - Background daemons: proactive check-in enabled
#    - Full routing available (web, AI, automation)
#
#  This is the "resting state" - everything works normally.
# =============================================================

from typing import Callable, Optional
from Backend.Utils.Logger import get_logger
from Backend.Core.ModeManager import mode_manager, Mode

log = get_logger("NeuralMode")

class NeuralMode:
    """Default mode - everything normal."""
    
    def __init__(self):
        self.active = False
    
    def enter(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        """Called when entering Neural mode."""
        self.active = True
        info = mode_manager.current_info
        
        announce = info["voice_announce"]
        log.info("Neural mode entered")
        
        if on_speak:
            on_speak(announce)
        
        return announce
    
    def exit(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        """Called when leaving Neural mode."""
        self.active = False
        log.info("Neural mode exited")
        msg = "Leaving neural mode, Sir."
        if on_speak:
            on_speak(msg)
        return msg
    
    def is_active(self) -> bool:
        return self.active and mode_manager.current_mode == Mode.NEURAL
    
    def get_greeting_tone(self) -> str:
        """Tone hint for Chatbot LLM when in Neural."""
        return "Standard Iron Man formal-warm tone. Sarcasm level 7."

# Singleton
neural_mode = NeuralMode()

if __name__ == "__main__":
    print("\n--- NeuralMode Test ---\n")
    
    def speak(msg):
        print(f"  [SPEAK] {msg}")
    
    mode_manager.switch(Mode.NEURAL)
    neural_mode.enter(on_speak=speak)
    print(f"Active: {neural_mode.is_active()}")
    print(f"Tone  : {neural_mode.get_greeting_tone()}")
    
    print("\n[OK] NeuralMode test complete\n")