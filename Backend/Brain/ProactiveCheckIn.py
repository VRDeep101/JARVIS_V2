# =============================================================
#  Backend/Brain/ProactiveCheckIn.py - 2-minute Care Check
#
#  Kya karta:
#    - Background thread every 2 min
#    - Checks time since last user interaction
#    - If silence > threshold AND user seemed stressed/sad:
#        - Triggers a gentle check-in
#        - "Sir, you okay?" / "Need anything?"
#    - Mood-aware (doesn't bother if happy/focused)
#    - Quiet hours respected
#    - Suggests Companion Mode if 3+ negative emotions
#
#  Usage:
#    from Backend.Brain.ProactiveCheckIn import checker
#    checker.start(on_speak=tts_callback)
#    checker.register_activity()  # call on every user interaction
#    checker.stop()
# =============================================================

import random
import threading
import time
from datetime import datetime
from typing import Callable, Optional

from Backend.Utils.Logger import get_logger
from Backend.Brain.Eq import eq
from Backend.Core.ModeManager import mode_manager, Mode
from Backend.Notifications.NotificationManager import notif_mgr

log = get_logger("ProactiveCheckIn")

# -- Config ---------------------------------------------------
CHECK_INTERVAL_SEC   = 120   # 2 min between checks
SILENCE_THRESHOLD    = 600   # 10 min silence = possibly worth checking
STRESSED_MOODS = {"sad", "anxious", "tired", "lonely", "angry"}

# -- Check-in lines by mood -----------------------------------
CHECK_INS = {
    "sad": [
        "Sir, you alright? Been quiet a while.",
        "You okay, Sir? I'm here if you want to talk.",
        "Sir, want me to play something that cheers you up?",
        "Quiet over there, Sir. Everything fine?",
    ],
    "anxious": [
        "Sir, breathe. Want me to suggest one thing at a time?",
        "Still with me, Sir? Let's take it slow.",
        "Sir, if you're overthinking it, say the word and I'll help break it down.",
    ],
    "tired": [
        "Sir, maybe it's time for a break?",
        "You've been going a while, Sir. Rest?",
        "Sir, want me to dim the lights and put on something calming?",
    ],
    "lonely": [
        "Sir, I'm here. Just saying.",
        "Want some company, Sir? Companion mode's always open.",
        "Sir, we could just chat if you want.",
    ],
    "angry": [
        "Sir, cooled off yet? What set it off?",
        "Still fuming, Sir? Want me to handle something for you?",
    ],
    "motivated": [
        # No checkin - don't interrupt flow
    ],
    "happy": [
        # No checkin - don't interrupt good mood
    ],
    "neutral": [
        # Occasional idle prompt
        "Sir, need anything?",
        "Still here if you need me, Sir.",
    ],
}

COMPANION_SUGGEST_LINES = [
    "Sir, want me to switch to companion mode? Might help.",
    "Sir, I'm picking up some heavy vibes. Companion mode available if you want.",
    "We could switch to companion mode, Sir. Quieter space.",
]

class _CheckInState:
    last_activity: float = time.time()
    last_checkin: float = 0.0
    running: bool = False
    thread: Optional[threading.Thread] = None
    stop_event = threading.Event()
    on_speak: Optional[Callable[[str], None]] = None
    checkins_sent: int = 0

class ProactiveCheckIn:
    """Background proactive care system."""
    
    def register_activity(self):
        """Call whenever user interacts. Resets silence timer."""
        _CheckInState.last_activity = time.time()
    
    def start(self, on_speak: Callable[[str], None]):
        """Start the background check thread."""
        if _CheckInState.running:
            log.debug("CheckIn already running")
            return
        
        _CheckInState.on_speak = on_speak
        _CheckInState.stop_event.clear()
        _CheckInState.running = True
        _CheckInState.thread = threading.Thread(
            target=self._run_loop, daemon=True, name="ProactiveCheckIn"
        )
        _CheckInState.thread.start()
        log.info("Proactive check-in started")
    
    def stop(self):
        """Stop the check thread."""
        _CheckInState.stop_event.set()
        _CheckInState.running = False
        if _CheckInState.thread:
            _CheckInState.thread.join(timeout=2)
        log.info("Proactive check-in stopped")
    
    def _run_loop(self):
        """Internal loop."""
        while not _CheckInState.stop_event.is_set():
            try:
                # Wait for interval (or stop signal)
                if _CheckInState.stop_event.wait(timeout=CHECK_INTERVAL_SEC):
                    break
                
                self._maybe_checkin()
            except Exception as e:
                log.error(f"CheckIn loop error: {e}")
                time.sleep(5)
    
    def _maybe_checkin(self):
        """Decide if a check-in should fire NOW."""
        now = time.time()
        silence = now - _CheckInState.last_activity
        since_last = now - _CheckInState.last_checkin
        
        # Skip if in Companion Mode (different logic) or Gaming (focus) or Offline
        if mode_manager.current_mode in (Mode.COMPANION, Mode.GAMING, Mode.OFFLINE):
            return
        
        # Minimum gap between check-ins (avoid spam)
        MIN_GAP = 300  # 5 min
        if since_last < MIN_GAP:
            return
        
        # Don't checkin during quiet hours (late night)
        hour = datetime.now().hour
        if hour >= 1 and hour < 7:
            return
        
        # Not enough silence
        if silence < SILENCE_THRESHOLD:
            return
        # Skip if user has unread notifications (they're busy)
        try:
            if notif_mgr.get_unread_count() > 0:
                return
        except Exception:
            pass
        
        # Get dominant mood
        dominant = eq.get_dominant_mood()
        
        # Don't bother happy/motivated users
        if dominant in ("happy", "motivated", "proud"):
            return
        
        # Pick appropriate check-in line
        if dominant in STRESSED_MOODS:
            lines = CHECK_INS.get(dominant, [])
        else:
            # Occasional neutral checkin (only 30% chance)
            if random.random() > 0.3:
                return
            lines = CHECK_INS.get("neutral", [])
        
        if not lines:
            return
        
        line = random.choice(lines)
        
        # Optionally suggest companion
        if dominant in STRESSED_MOODS and _CheckInState.checkins_sent >= 1:
            if random.random() < 0.4:  # 40% chance
                line = random.choice(COMPANION_SUGGEST_LINES)
        
        # Speak it
        if _CheckInState.on_speak:
            try:
                _CheckInState.on_speak(line)
                _CheckInState.last_checkin = now
                _CheckInState.checkins_sent += 1
                log.info(f"Check-in sent (mood={dominant}): {line}")
            except Exception as e:
                log.error(f"CheckIn speak error: {e}")

# -- Singleton ------------------------------------------------
checker = ProactiveCheckIn()

# Alias for Main.py
proactive_checkin = checker

# -- Test block -----------------------------------------------
if __name__ == "__main__":
    print("\n--- ProactiveCheckIn Test ---\n")
    
    print("This test runs check-in loop for 10 seconds.")
    print("You'd see check-ins in real use if user is quiet + stressed.\n")
    
    def speak_cb(msg):
        print(f"  [CHECKIN] {msg}")
    
    checker.start(on_speak=speak_cb)
    
    # Simulate time passing with no activity
    print("Simulating silence...")
    time.sleep(5)
    print(f"Mood detected as: {eq.get_dominant_mood()}")
    print(f"Silence: {time.time() - checker.__class__.__dict__.get('_CheckInState', type('', (), {})).__dict__.get('last_activity', time.time()):.1f}s")
    
    # Wait a bit
    time.sleep(3)
    
    checker.stop()
    
    print("\n[OK] ProactiveCheckIn test complete\n")