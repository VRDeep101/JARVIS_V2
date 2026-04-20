# =============================================================
#  Backend/Core/ContextManager.py - 25-msg + 3-day Memory
#
#  Kya karta:
#    - Last 25 messages track karta (current session)
#    - Last 3 days ki chats preserve karta (cross-session)
#    - Ambiguous queries resolve karta ("open it" -> last app)
#    - Follow-up detection ("now search X" -> continues prev action)
#    - Self-echo detection (Jarvis khud ka response na sune)
#    - Repeat detection (same query 3 times -> clarification)
#    - Companion conversations alag-alag track
#
#  Usage:
#    from Backend.Core.ContextManager import context
#    context.add_user(query)
#    context.add_assistant(response)
#    context.get_recent(n=10)
#    context.is_repeat(query)
#    context.is_self_echo(text)
#    context.resolve_pronoun("open it") -> "open chrome"
# =============================================================

import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Core.ModeManager import mode_manager, Mode

log = get_logger("Context")

# -- Config ---------------------------------------------------
SHORT_TERM_SIZE = 25     # last N messages (current session)
CROSS_SESSION_DAYS = 3   # how many days back to keep
REPEAT_THRESHOLD = 3     # same query N times -> warn
ECHO_MATCH_RATIO = 0.70  # 70%+ word match = self-echo

# -- Paths ----------------------------------------------------
CHAT_LOG_PATH = paths.CHAT_LOG                  # Data/ChatLog.json
CROSS_SESSION_PATH = paths.DATA_DIR / "cross_session_chat.json"
COMPANION_CHAT_PATH = paths.DATA_DIR / "companion_chat.json"  # companion only

# -- State ----------------------------------------------------
class _ContextState:
    short_term: List[Dict] = []      # current session messages
    recent_queries: List[str] = []   # last 20 user queries (for repeat detect)
    recent_tts: List[str] = []       # last 5 TTS outputs (for echo detect)
    last_action: Optional[Dict] = None  # last executed action (for pronoun resolve)
    session_start: str = ""
    _lock = threading.Lock()

# -- ContextManager class -------------------------------------
class ContextManager:
    """Central context tracker."""
    
    def __init__(self):
        _ContextState.session_start = datetime.now().isoformat()
        self._load_recent()
    
    # -- Internal: load recent history --------------------
    def _load_recent(self):
        """Load last 3 days of chats at startup."""
        path = self._active_chat_path()
        if not path.exists():
            _ContextState.short_term = []
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                all_msgs = json.load(f)
            
            if not isinstance(all_msgs, list):
                all_msgs = []
            
            # Keep last SHORT_TERM_SIZE for immediate context
            _ContextState.short_term = all_msgs[-SHORT_TERM_SIZE:]
            log.info(f"Loaded {len(_ContextState.short_term)} recent messages")
        
        except Exception as e:
            log.error(f"Context load error: {e}")
            _ContextState.short_term = []
    
    def _active_chat_path(self) -> Path:
        """Return chat path based on current mode (companion has separate log)."""
        if mode_manager.is_companion():
            return COMPANION_CHAT_PATH
        return CHAT_LOG_PATH
    
    # -- Adding messages ----------------------------------
    def add_user(self, query: str):
        """Add user query to context."""
        if not query or not query.strip():
            return
        
        with _ContextState._lock:
            entry = {
                "role": "user",
                "content": query.strip(),
                "timestamp": datetime.now().isoformat(),
                "mode": mode_manager.current_mode.value,
            }
            _ContextState.short_term.append(entry)
            _ContextState.recent_queries.append(query.lower().strip())
            
            # Trim lists
            _ContextState.short_term = _ContextState.short_term[-SHORT_TERM_SIZE:]
            _ContextState.recent_queries = _ContextState.recent_queries[-20:]
        
        self._persist()
    
    def add_assistant(self, response: str):
        """Add Jarvis response to context."""
        if not response or not response.strip():
            return
        
        with _ContextState._lock:
            entry = {
                "role": "assistant",
                "content": response.strip(),
                "timestamp": datetime.now().isoformat(),
                "mode": mode_manager.current_mode.value,
            }
            _ContextState.short_term.append(entry)
            _ContextState.recent_tts.append(response.lower().strip())
            
            _ContextState.short_term = _ContextState.short_term[-SHORT_TERM_SIZE:]
            _ContextState.recent_tts = _ContextState.recent_tts[-5:]
        
        self._persist()
    
    def set_last_action(self, action: str, details: dict = None):
        """
        Track last executed action (for pronoun resolution).
        E.g. after opening Chrome: set_last_action("open", {"app": "chrome"})
        """
        with _ContextState._lock:
            _ContextState.last_action = {
                "action": action,
                "details": details or {},
                "timestamp": time.time(),
            }
    
    # -- Retrieval ----------------------------------------
    def get_recent(self, n: int = 10) -> List[Dict]:
        """Return last N messages (both roles)."""
        with _ContextState._lock:
            return list(_ContextState.short_term[-n:])
    
    def get_for_llm(self, n: int = 20) -> List[Dict]:
        """
        Format for LLM: just {role, content} (strip timestamps).
        """
        msgs = self.get_recent(n)
        return [{"role": m["role"], "content": m["content"]} for m in msgs]
    
    def get_last_user(self) -> Optional[str]:
        """Last user query (or None)."""
        with _ContextState._lock:
            for m in reversed(_ContextState.short_term):
                if m["role"] == "user":
                    return m["content"]
        return None
    
    def get_last_assistant(self) -> Optional[str]:
        """Last Jarvis response."""
        with _ContextState._lock:
            for m in reversed(_ContextState.short_term):
                if m["role"] == "assistant":
                    return m["content"]
        return None
    
    # -- Detection helpers --------------------------------
    def is_repeat(self, query: str) -> bool:
        """True if this query seen 3+ times recently."""
        q_norm = query.lower().strip()
        with _ContextState._lock:
            count = _ContextState.recent_queries.count(q_norm)
        return count >= REPEAT_THRESHOLD
    
    def is_self_echo(self, text: str) -> bool:
        """
        True if text looks like something Jarvis just said.
        Used by STT to block mic picking up TTS.
        """
        if not text or not text.strip():
            return False
        
        words = set(text.lower().strip().split())
        if not words:
            return False
        
        with _ContextState._lock:
            tts_history = list(_ContextState.recent_tts)
        
        for tts_text in tts_history:
            tts_words = set(tts_text.split())
            if not tts_words:
                continue
            overlap = len(words & tts_words)
            ratio = overlap / len(words)
            if ratio >= ECHO_MATCH_RATIO:
                return True
        return False
    
    def register_tts(self, text: str):
        """Alias for cleaner imports. Same as passing to add_assistant."""
        with _ContextState._lock:
            _ContextState.recent_tts.append(text.lower().strip())
            _ContextState.recent_tts = _ContextState.recent_tts[-5:]
    
    def clear_tts_cache(self):
        """Clear echo cache (e.g. after TTS finishes)."""
        with _ContextState._lock:
            _ContextState.recent_tts.clear()
    
    # -- Pronoun / follow-up resolver ---------------------
    def resolve_pronoun(self, query: str) -> str:
        """
        Expand ambiguous pronouns using last action.
        'open it' + last='chrome' -> 'open chrome'
        'close that' -> 'close [last app]'
        'search it on youtube' -> 'search [last thing] on youtube'
        """
        q = query.lower().strip()
        last = _ContextState.last_action
        if not last:
            return query
        
        # Check if too old (> 2 minutes)
        if time.time() - last["timestamp"] > 120:
            return query
        
        details = last.get("details", {})
        subject = details.get("app") or details.get("subject") or details.get("query", "")
        
        pronouns = ["it", "that", "this", "wo", "yeh"]
        for pn in pronouns:
            # Match patterns like "open it", "close that"
            patterns = [f" {pn} ", f" {pn}.", f" {pn}?", f" {pn}!", f" {pn}"]
            for p in patterns:
                if q.endswith(p.strip()) or p in q:
                    if subject:
                        replaced = q.replace(p.strip(), subject)
                        log.debug(f"Resolved pronoun: '{query}' -> '{replaced}'")
                        return replaced
        return query
    
    def is_follow_up(self, query: str) -> bool:
        """
        Detect follow-up commands: "now X", "next Y", "also Z".
        Used to chain actions.
        """
        q = query.lower().strip()
        follow_up_starters = [
            "now ", "next ", "also ", "then ", "after that", "and then",
            "ab ", "ab iske baad", "phir ", "uske baad",
        ]
        return any(q.startswith(s) for s in follow_up_starters)
    
    # -- Persistence --------------------------------------
    def _persist(self):
        """Save short-term to disk."""
        path = self._active_chat_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(_ContextState.short_term, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Persist error: {e}")
    
    # -- Cross-session retrieval --------------------------
    def get_cross_session_summary(self, days: int = CROSS_SESSION_DAYS) -> str:
        """
        Summary of chats from last N days (for LLM context).
        Returns readable text, not full messages.
        """
        path = CROSS_SESSION_PATH
        if not path.exists():
            return ""
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                all_msgs = json.load(f)
            
            cutoff = datetime.now() - timedelta(days=days)
            recent = []
            for m in all_msgs:
                try:
                    ts = datetime.fromisoformat(m.get("timestamp", ""))
                    if ts >= cutoff:
                        recent.append(m)
                except Exception:
                    continue
            
            if not recent:
                return ""
            
            # Take last 15 for summary
            tail = recent[-15:]
            lines = [f"{m['role']}: {m['content'][:80]}" for m in tail]
            return "Recent conversations (last 3 days):\n" + "\n".join(lines)
        
        except Exception as e:
            log.error(f"Cross-session load error: {e}")
            return ""
    
    def archive_to_cross_session(self):
        """
        Move current session to cross-session archive.
        Called at session end or periodically.
        """
        if not _ContextState.short_term:
            return
        
        try:
            existing = []
            if CROSS_SESSION_PATH.exists():
                with open(CROSS_SESSION_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            
            if not isinstance(existing, list):
                existing = []
            
            # Combine, dedupe by timestamp
            seen = set()
            merged = []
            for m in existing + _ContextState.short_term:
                ts = m.get("timestamp", "")
                if ts and ts not in seen:
                    seen.add(ts)
                    merged.append(m)
            
            # Prune to last 3 days
            cutoff = datetime.now() - timedelta(days=CROSS_SESSION_DAYS)
            pruned = []
            for m in merged:
                try:
                    ts = datetime.fromisoformat(m.get("timestamp", ""))
                    if ts >= cutoff:
                        pruned.append(m)
                except Exception:
                    continue
            
            with open(CROSS_SESSION_PATH, "w", encoding="utf-8") as f:
                json.dump(pruned, f, indent=2, ensure_ascii=False)
            
            log.info(f"Archived. Cross-session now has {len(pruned)} messages")
        
        except Exception as e:
            log.error(f"Archive error: {e}")
    
    # -- Clear ---------------------------------------------
    def clear_session(self):
        """Clear current session only (not cross-session archive)."""
        with _ContextState._lock:
            _ContextState.short_term = []
            _ContextState.recent_queries.clear()
            _ContextState.recent_tts.clear()
        self._persist()
        log.info("Session cleared")
    
    def clear_all(self, preserve_companion: bool = True):
        """
        Nuke all context. Used by 'clear data' command.
        preserve_companion: if True, companion chat stays.
        """
        self.clear_session()
        try:
            if CROSS_SESSION_PATH.exists():
                CROSS_SESSION_PATH.unlink()
            if not preserve_companion and COMPANION_CHAT_PATH.exists():
                COMPANION_CHAT_PATH.unlink()
            log.info("All context cleared")
        except Exception as e:
            log.error(f"Clear all error: {e}")

# -- Singleton ------------------------------------------------
context = ContextManager()

# -- Test block -----------------------------------------------
if __name__ == "__main__":
    print("\n--- ContextManager Test ---\n")
    
    # Add some messages
    context.add_user("hello jarvis")
    context.add_assistant("Hello Sir, at your service.")
    context.add_user("what's the weather")
    context.add_assistant("Currently 28 degrees in Pune, Sir.")
    context.add_user("open chrome")
    context.set_last_action("open", {"app": "chrome"})
    context.add_assistant("Chrome opened, Sir.")
    
    # Recent
    print(f"Last 4 messages:")
    for m in context.get_recent(4):
        print(f"  [{m['role']:9}] {m['content'][:50]}")
    
    # For LLM
    llm_msgs = context.get_for_llm(3)
    print(f"\nLLM format (last 3): {len(llm_msgs)} msgs")
    
    # Last queries
    print(f"\nLast user    : {context.get_last_user()}")
    print(f"Last assistant: {context.get_last_assistant()}")
    
    # Pronoun resolve
    print("\n-- Pronoun resolution --")
    test = [
        ("close it", "chrome"),
        ("open that", "chrome"),
        ("what is the weather", "unchanged"),
    ]
    for q, _ in test:
        resolved = context.resolve_pronoun(q)
        print(f"  '{q}' -> '{resolved}'")
    
    # Follow-up
    print("\n-- Follow-up detection --")
    for q in ["now open spotify", "hello", "ab volume up kar", "what time is it"]:
        print(f"  '{q}' -> follow_up={context.is_follow_up(q)}")
    
    # Repeat detection
    print("\n-- Repeat detection --")
    for _ in range(3):
        context.add_user("what time is it")
    print(f"  'what time is it' (asked 3x) -> repeat={context.is_repeat('what time is it')}")
    print(f"  'new question' -> repeat={context.is_repeat('new question')}")
    
    # Self-echo
    print("\n-- Self-echo detection --")
    context.register_tts("Opening Chrome for you Sir")
    print(f"  'opening chrome for you sir' -> echo={context.is_self_echo('opening chrome for you sir')}")
    print(f"  'what is the weather' -> echo={context.is_self_echo('what is the weather')}")
    
    print("\n[OK] ContextManager test complete\n")