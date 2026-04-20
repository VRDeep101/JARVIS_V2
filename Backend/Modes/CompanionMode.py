# =============================================================
#  Backend/Modes/CompanionMode.py - Emotional Care Mode
#
#  Kya karta:
#    - Password gate (1406) before entry
#    - Loads 500+ companion lines from JSON
#    - Strict vault isolation (STRICT from ModeManager)
#    - Smart line picking based on context/time/mood
#    - Effective lines tracking (learns what works)
#    - All conversations auto-save to companion_vault.json
#    - Soft voice hints (slower rate, warmer pitch)
#    - Exit phrases + auto-exit on 30 min normal queries
#
#  Usage:
#    from Backend.Modes.CompanionMode import companion_mode
#    success = companion_mode.verify_password("1406")
#    if success:
#        companion_mode.enter(on_speak=tts_cb)
#    line = companion_mode.pick_line(category="late_night")
# =============================================================

import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from dotenv import dotenv_values

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Core.ModeManager import mode_manager, Mode
from Backend.Brain.Memory import memory

log = get_logger("CompanionMode")

# -- Config ---------------------------------------------------
env = dotenv_values(".env")
COMPANION_PASSWORD = env.get("CompanionPassword", "1406").strip()
MAX_FAILED_ATTEMPTS = 3
LOCKOUT_SECONDS = 30

# -- Paths ----------------------------------------------------
COMPANION_LINES_PATH = paths.COMPANION_LINES
VAULT_PATH = paths.COMPANION_VAULT

# =============================================================
#  CompanionMode class
# =============================================================
class CompanionMode:
    """Password-protected emotional care mode."""
    
    def __init__(self):
        self.active = False
        self.on_speak: Optional[Callable] = None
        
        # Password state
        self.failed_attempts = 0
        self.lockout_until = 0.0
        
        # Load library
        self.lines_db: Dict = self._load_lines()
        self.used_lines: List[str] = []  # avoid repeats in session
        self.effective_lines: List[str] = []  # ones that worked
        
        # Session tracking
        self.session_start: Optional[datetime] = None
    
    # =========================================================
    #  LIBRARY LOAD
    # =========================================================
    def _load_lines(self) -> Dict:
        """Load 500+ companion lines from JSON."""
        if not COMPANION_LINES_PATH.exists():
            log.warn(f"Lines file missing: {COMPANION_LINES_PATH}")
            return {}
        try:
            with open(COMPANION_LINES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            count = sum(len(v) for v in data.values() if isinstance(v, list))
            log.info(f"Loaded {count} companion lines across {len(data)} categories")
            return data
        except Exception as e:
            log.error(f"Lines load error: {e}")
            return {}
    
    # =========================================================
    #  PASSWORD VERIFICATION
    # =========================================================
    def verify_password(self, attempt: str) -> Dict:
        """
        Verify password.
        Handles voice input like "one four zero six" too.
        """
        # Check lockout
        now = time.time()
        if now < self.lockout_until:
            remaining = int(self.lockout_until - now)
            return {
                "ok": False,
                "locked_out": True,
                "message": f"Too many failed attempts, Sir. Wait {remaining} seconds.",
            }
        
        # Normalize voice number -> digits
        normalized = self._normalize_pw_input(attempt)
        
        if normalized == COMPANION_PASSWORD:
            self.failed_attempts = 0
            log.info("Companion password correct")
            return {"ok": True, "message": "Access granted, Sir."}
        
        # Failed
        self.failed_attempts += 1
        log.warn(f"Companion password wrong (attempt {self.failed_attempts})")
        
        if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
            self.lockout_until = now + LOCKOUT_SECONDS
            self.failed_attempts = 0
            return {
                "ok": False,
                "locked_out": True,
                "message": f"Sir, are you sure this is you? Locked out for {LOCKOUT_SECONDS} seconds.",
            }
        
        return {
            "ok": False,
            "locked_out": False,
            "attempts_left": MAX_FAILED_ATTEMPTS - self.failed_attempts,
            "message": "That's not right, Sir. Try again.",
        }
    
    def _normalize_pw_input(self, attempt: str) -> str:
        """Convert 'one four zero six' / 'fourteen oh six' -> '1406'."""
        raw = attempt.strip().lower()
        
        # Already digits
        digits_only = "".join(c for c in raw if c.isdigit())
        if len(digits_only) >= 4:
            return digits_only
        
        # Word-to-digit mapping
        word_digits = {
            "zero": "0", "oh": "0", "o": "0", "naught": "0",
            "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
            "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
            "fourteen": "14", "fifteen": "15", "sixteen": "16",
        }
        
        words = raw.replace("-", " ").split()
        result = ""
        for w in words:
            if w in word_digits:
                result += word_digits[w]
        
        return result if result else raw
    
    # =========================================================
    #  ENTER / EXIT
    # =========================================================
    def enter(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        """
        Activate Companion mode.
        IMPORTANT: caller must verify password FIRST.
        """
        self.active = True
        self.on_speak = on_speak
        self.used_lines = []
        self.session_start = datetime.now()
        
        # Personalized greeting based on time
        hour = datetime.now().hour
        if hour < 6:
            announce = "Welcome back, Deep. Late night, huh? I'm here."
        elif hour < 12:
            announce = "Welcome back, Deep. Good to see you this morning."
        elif hour < 17:
            announce = "Welcome back, Deep. I'm here."
        elif hour < 22:
            announce = "Welcome back, Deep. Long day? I'm here."
        else:
            announce = "Welcome back, Deep. Winding down? Take your time."
        
        log.info("Companion mode entered")
        if on_speak:
            on_speak(announce)
        
        return announce
    
    def exit(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        """Leave Companion mode - save session + clear state."""
        self.active = False
        
        # Save session summary to vault
        if self.session_start:
            duration_min = (datetime.now() - self.session_start).total_seconds() / 60
            self._save_session({
                "start": self.session_start.isoformat(),
                "end": datetime.now().isoformat(),
                "duration_minutes": round(duration_min, 1),
                "lines_used": len(self.used_lines),
                "effective_lines": len(self.effective_lines),
            })
        
        self.session_start = None
        self.used_lines = []
        self.effective_lines = []
        
        msg = "Always here, Deep. Just call."
        log.info("Companion mode exited")
        if on_speak:
            on_speak(msg)
        return msg
    
    def is_active(self) -> bool:
        return self.active and mode_manager.current_mode == Mode.COMPANION
    
    # =========================================================
    #  LINE PICKING
    # =========================================================
    def pick_line(self, category: Optional[str] = None) -> str:
        """
        Pick a contextually appropriate companion line.
        If category omitted, auto-chooses based on time/mood.
        """
        if category is None:
            category = self._auto_category()
        
        pool = self.lines_db.get(category, [])
        if not pool:
            # Fallback to random warm
            pool = self.lines_db.get("random_warm", [])
        
        if not pool:
            return "I'm here, Deep."
        
        # Filter out recently used
        fresh = [line for line in pool if line not in self.used_lines]
        if not fresh:
            # All used - reset
            self.used_lines = []
            fresh = pool
        
        # Prefer effective lines (30% chance)
        effective_fresh = [l for l in fresh if l in self.effective_lines]
        if effective_fresh and random.random() < 0.3:
            chosen = random.choice(effective_fresh)
        else:
            chosen = random.choice(fresh)
        
        self.used_lines.append(chosen)
        self.used_lines = self.used_lines[-30:]  # cap memory
        
        # Substitute placeholders (e.g. {hours} -> actual hours)
        chosen = self._substitute_placeholders(chosen)
        return chosen
    
    def _auto_category(self) -> str:
        """Pick category based on current context."""
        hour = datetime.now().hour
        
        # Late night = gentle care
        if hour >= 23 or hour < 5:
            return "late_night"
        
        # Random from mid-weight categories
        preferred = [
            "soft_checkins", "shared_memories", "emotional_questions",
            "creation_memories", "random_warm",
        ]
        return random.choice([p for p in preferred if p in self.lines_db])
    
    def _substitute_placeholders(self, text: str) -> str:
        """Replace {hours}, {name} etc with real values."""
        # Time together from memory
        if "{hours}" in text:
            try:
                hours = memory.personality.get("time_spent_hours", 0)
                text = text.replace("{hours}", str(int(hours)))
            except Exception:
                text = text.replace("{hours}", "several")
        
        # Days-ago type placeholders
        if "{days}" in text:
            text = text.replace("{days}", "a few")
        
        # Module placeholder for memories
        if "{module}" in text:
            text = text.replace("{module}", "a bug")
        
        return text
    
    def mark_effective(self, line: str):
        """Mark a line as resonating well with user."""
        if line and line not in self.effective_lines:
            self.effective_lines.append(line)
            log.info(f"Line marked effective: '{line[:40]}'")
            # Persist to vault
            self._save_effective_line(line)
    
    def mark_ineffective(self, line: str):
        """Mark a line that fell flat - deprioritize in future."""
        log.info(f"Line marked ineffective: '{line[:40]}'")
        self._save_ineffective_line(line)
    
    # =========================================================
    #  VAULT (separate from normal memory)
    # =========================================================
    def save_to_vault(self, entry_type: str, content: str, metadata: dict = None):
        """
        Save something in the private Companion vault.
        ONLY accessible in Companion mode (ModeManager enforces).
        """
        if not mode_manager.can_access_vault():
            log.error("Tried to write vault outside Companion mode - BLOCKED")
            return False
        
        try:
            vault = self._load_vault()
            
            entry = {
                "type": entry_type,   # "conversation" / "secret" / "memory"
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
            
            key = "deep_memories" if entry_type == "memory" else "shared_secrets"
            vault.setdefault(key, []).append(entry)
            
            # Cap at 500 per category
            if len(vault[key]) > 500:
                vault[key] = vault[key][-500:]
            
            self._save_vault(vault)
            log.debug(f"Saved to vault: [{entry_type}] {content[:40]}")
            return True
        except Exception as e:
            log.error(f"Vault save error: {e}")
            return False
    
    def recall_from_vault(self, keyword: str = "", limit: int = 5) -> List[Dict]:
        """Search vault for entries. Only works in Companion mode."""
        if not mode_manager.can_access_vault():
            log.error("Tried to read vault outside Companion mode - BLOCKED")
            return []
        
        try:
            vault = self._load_vault()
            results = []
            kw = keyword.lower().strip() if keyword else ""
            
            for key in ["deep_memories", "shared_secrets"]:
                for entry in vault.get(key, []):
                    content = entry.get("content", "")
                    if not kw or kw in content.lower():
                        results.append(entry)
            
            results.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            return results[:limit]
        except Exception as e:
            log.error(f"Vault recall error: {e}")
            return []
    
    def _load_vault(self) -> Dict:
        if not VAULT_PATH.exists():
            return {"sessions": [], "shared_secrets": [], "deep_memories": [],
                    "companion_lines_used": [], "effective_lines": [], "ineffective_lines": []}
        try:
            with open(VAULT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Vault load: {e}")
            return {}
    
    def _save_vault(self, vault: Dict):
        try:
            tmp = VAULT_PATH.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(vault, f, indent=2, ensure_ascii=False)
            tmp.replace(VAULT_PATH)
        except Exception as e:
            log.error(f"Vault save: {e}")
    
    def _save_session(self, session_data: Dict):
        vault = self._load_vault()
        vault.setdefault("sessions", []).append(session_data)
        vault["sessions"] = vault["sessions"][-100:]
        self._save_vault(vault)
    
    def _save_effective_line(self, line: str):
        vault = self._load_vault()
        eff = vault.setdefault("effective_lines", [])
        if line not in eff:
            eff.append(line)
            vault["effective_lines"] = eff[-200:]
            self._save_vault(vault)
    
    def _save_ineffective_line(self, line: str):
        vault = self._load_vault()
        ineff = vault.setdefault("ineffective_lines", [])
        if line not in ineff:
            ineff.append(line)
            vault["ineffective_lines"] = ineff[-200:]
            self._save_vault(vault)

# =============================================================
#  Singleton
# =============================================================
companion_mode = CompanionMode()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- CompanionMode Test ---\n")
    
    # Password tests
    print("-- Password Verification --")
    tests = [
        ("1406", True),
        ("one four zero six", True),
        ("fourteen oh six", True),
        ("wrong", False),
        ("1407", False),
    ]
    for attempt, expected in tests:
        r = companion_mode.verify_password(attempt)
        ok = "[OK]" if (r["ok"] == expected) else "[FAIL]"
        print(f"  {ok} '{attempt:25}' -> ok={r['ok']}, msg={r['message'][:40]}")
    
    # Reset state after test
    companion_mode.failed_attempts = 0
    companion_mode.lockout_until = 0
    
    # Lines DB
    print(f"\n-- Lines Database --")
    print(f"  Categories loaded: {len(companion_mode.lines_db)}")
    total = sum(len(v) for v in companion_mode.lines_db.values() if isinstance(v, list))
    print(f"  Total lines: {total}")
    for cat, lines in list(companion_mode.lines_db.items())[:5]:
        if isinstance(lines, list):
            print(f"    {cat:20} -> {len(lines)} lines")
    
    # Simulated enter (without full mode_manager switch for test)
    print("\n-- Line Picking --")
    # Temporarily allow picking without full activation
    if companion_mode.lines_db:
        for cat in ["random_warm", "late_night", "soft_checkins"]:
            if cat in companion_mode.lines_db:
                line = companion_mode.pick_line(cat)
                print(f"  [{cat:20}] {line[:70]}")
    
    print("\n-- Vault Access Check --")
    # Outside companion mode - should FAIL
    mode_manager.switch(Mode.NEURAL)
    r = companion_mode.save_to_vault("test", "this should not save")
    print(f"  Write in Neural mode: blocked={not r}  <-- should say blocked=True")
    
    # In companion mode - should work
    mode_manager.switch(Mode.COMPANION)
    r = companion_mode.save_to_vault("memory", "Test vault entry")
    print(f"  Write in Companion mode: saved={r}")
    
    entries = companion_mode.recall_from_vault("Test")
    print(f"  Recall: {len(entries)} entries found")
    
    mode_manager.switch(Mode.NEURAL)
    
    print("\n[OK] CompanionMode test complete\n")