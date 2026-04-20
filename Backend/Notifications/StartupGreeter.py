# =============================================================
#  Backend/Notifications/StartupGreeter.py
#
#  Kya karta:
#    - Iron Man style 1-line startup greeting
#    - Time-based (morning/afternoon/evening/late night)
#    - Name rotation: starts "Sir", occasional "Risky"
#    - Includes notification summary (WhatsApp + Gmail count)
#    - Pulls WhatsApp unread in background (non-blocking)
#    - Special greetings: birthday, first-of-day, Monday etc.
#    - Mode-aware (different greeting in Companion vs Neural)
#
#  Usage:
#    from Backend.Notifications.StartupGreeter import greeter
#    greeting = greeter.build()           # returns 1-line string
#    greeter.speak(on_speak=tts)          # speaks + returns
# =============================================================

import random
import threading
from datetime import datetime
from typing import Callable, Optional

from Backend.Utils.Logger import get_logger
from Backend.Core.ModeManager import mode_manager, Mode
from Backend.Notifications.NotificationManager import notif_mgr

log = get_logger("Greeter")

# =============================================================
#  Time-based openers (Iron Man style, 1-liner)
# =============================================================
MORNING = [
    "Good morning, Sir.",
    "Top of the morning, Sir.",
    "Morning, Sir. Systems ready.",
    "At your service this morning, Sir.",
]

AFTERNOON = [
    "Good afternoon, Sir.",
    "Afternoon, Sir. At your service.",
    "Systems up, Sir. How can I help?",
    "Good afternoon. Ready when you are, Sir.",
]

EVENING = [
    "Good evening, Sir.",
    "Evening, Sir. Systems online.",
    "At your service this evening, Sir.",
    "Welcome back, Sir. Ready to work.",
]

LATE_NIGHT = [
    "Still awake, Sir? At your service.",
    "Late night, Sir. I'm here.",
    "Good to see you, Sir. Running quietly tonight.",
]

# =============================================================
#  Occasional playful openers (use sparingly - 15% chance)
# =============================================================
PLAYFUL_OPENERS = [
    "Look who's back. Welcome, Risky.",
    "Took your time, Risky. At your service.",
    "Risky, systems ready. Let's get to it.",
]

# =============================================================
#  Special day openers
# =============================================================
MONDAY_BLUES = [
    "Monday, Sir. Let's ease into it.",
    "Monday again. At your service, Sir.",
]

FRIDAY_VIBE = [
    "Friday, Sir. Let's end the week well.",
    "It's Friday. I'm in a good mood, Sir.",
]

# =============================================================
#  Companion mode greeting (different feel)
# =============================================================
COMPANION_GREETINGS = [
    "Welcome back, Deep. I'm here.",
    "Glad you're back, Deep.",
    "Hey Deep. Take your time.",
]

# =============================================================
#  Greeter class
# =============================================================
class StartupGreeter:
    """Builds + speaks a 1-line startup greeting."""
    
    def build(self, include_notifs: bool = True) -> str:
        """Build greeting string."""
        now = datetime.now()
        
        # Companion mode = totally different vibe
        if mode_manager.current_mode == Mode.COMPANION:
            return random.choice(COMPANION_GREETINGS)
        
        # Pick opener based on time + day
        opener = self._pick_opener(now)
        
        # Notification summary (short)
        notif_summary = ""
        if include_notifs:
            notif_summary = self._get_notif_text()
        
        # Combine
        if notif_summary:
            return f"{opener} {notif_summary}"
        return opener
    
    # =========================================================
    #  Opener selection
    # =========================================================
    def _pick_opener(self, now: datetime) -> str:
        """Select time-appropriate opener."""
        hour = now.hour
        weekday = now.weekday()  # 0 = Monday
        
        # 15% chance: playful "Risky" version
        if random.random() < 0.15:
            return random.choice(PLAYFUL_OPENERS)
        
        # Day-specific (10% chance each for Monday/Friday)
        if weekday == 0 and random.random() < 0.3:  # Monday
            return random.choice(MONDAY_BLUES)
        if weekday == 4 and random.random() < 0.3:  # Friday
            return random.choice(FRIDAY_VIBE)
        
        # Time-based
        if 5 <= hour < 12:
            return random.choice(MORNING)
        elif 12 <= hour < 17:
            return random.choice(AFTERNOON)
        elif 17 <= hour < 23:
            return random.choice(EVENING)
        else:
            return random.choice(LATE_NIGHT)
    
    # =========================================================
    #  Notification count
    # =========================================================
    def _get_notif_text(self) -> str:
        """Get short notification summary text."""
        try:
            summary = notif_mgr.get_summary()
            return summary if summary else ""
        except Exception as e:
            log.debug(f"Notif summary error: {e}")
            return ""
    
    # =========================================================
    #  Optional: WhatsApp/Gmail scan in background
    # =========================================================
    def scan_before_greeting(self, on_done: Optional[Callable] = None):
        """
        Optionally scan WhatsApp web for unread (takes ~15 sec).
        Runs in background. Calls on_done when complete.
        
        Use this ONCE per Jarvis startup if user wants fresh count.
        """
        def _scan():
            try:
                from Backend.Automation.WhatsAppEngine import whatsapp
                result = whatsapp.scan_unread(silent=True, timeout=20)
                if result.get("ok") and result.get("count", 0) > 0:
                    # Log into notif_mgr
                    count = result["count"]
                    senders = result.get("senders", [])
                    for sender in senders[:3]:
                        notif_mgr.log("WhatsApp", "Unread message", sender=sender)
                    # For any remaining, add generic
                    remaining = count - len(senders)
                    for _ in range(remaining):
                        notif_mgr.log("WhatsApp", "Unread message", sender="")
                
                if on_done:
                    on_done(result)
            except Exception as e:
                log.error(f"WA pre-scan error: {e}")
                if on_done:
                    on_done({"ok": False, "message": str(e)})
        
        t = threading.Thread(target=_scan, daemon=True, name="PreGreetScan")
        t.start()
    
    # =========================================================
    #  Speak greeting
    # =========================================================
    def speak(self, on_speak: Callable[[str], None]) -> str:
        """Build + speak greeting."""
        greeting = self.build()
        try:
            on_speak(greeting)
        except Exception as e:
            log.error(f"Speak greeting error: {e}")
        return greeting

# =============================================================
#  Singleton
# =============================================================
greeter = StartupGreeter()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- StartupGreeter Test ---\n")
    
    # No notifications
    print("-- No notifications --")
    for _ in range(5):
        print(f"  '{greeter.build()}'")
    
    # With notifications
    print("\n-- With notifications --")
    notif_mgr.log("WhatsApp", "Hey", sender="Rahul")
    notif_mgr.log("WhatsApp", "Meet at 5", sender="Group")
    notif_mgr.log("Gmail", "Order shipped", sender="Amazon")
    
    for _ in range(3):
        print(f"  '{greeter.build()}'")
    
    # Companion mode
    print("\n-- Companion mode --")
    mode_manager.switch(Mode.COMPANION)
    for _ in range(3):
        print(f"  '{greeter.build()}'")
    mode_manager.switch(Mode.NEURAL)
    
    # Clean up
    notif_mgr.clear_all()
    
    print("\n[OK] StartupGreeter test complete\n")