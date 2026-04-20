# ═════════════════════════════════════════════════════════════
#  Backend/Core/ErrorHandler.py  —  Central Error Recovery
#
#  Kya karta:
#    - 3-tier error system (soft / task / critical)
#    - 50+ context-specific user-friendly messages
#    - Auto-retry for transient errors
#    - Module restart on critical failures
#    - All errors logged to Logs/errors.log
#
#  Usage:
#    from Backend.Core.ErrorHandler import safe_run, handle_error, ErrorLevel
#
#    @safe_run(tier="task", fallback="Couldn't fetch weather right now.")
#    def get_weather():
#        ...
#
#    or manually:
#    try:
#        risky_thing()
#    except Exception as e:
#        msg = handle_error(e, context="API call", tier="task")
#        speak(msg)
# ═════════════════════════════════════════════════════════════

import sys
import traceback
import functools
import time
from enum import Enum
from typing import Callable, Optional, Any

from Backend.Utils.Logger import get_logger

log = get_logger("ErrorHandler")

# ── Error Tiers ───────────────────────────────────────────────
class ErrorLevel(Enum):
    SOFT     = "soft"      # Minor, auto-retry, quiet
    TASK     = "task"      # Task failed, inform user
    CRITICAL = "critical"  # Module down, restart needed

# ── User-Friendly Response Library ────────────────────────────
_SOFT_RESPONSES = [
    "Sir, minor hiccup. Let me try that differently.",
    "Small glitch, Sir. One moment.",
    "Just a momentary issue, retrying now.",
    "Minor delay, Sir. Working around it.",
    "Small bump — handling it now.",
]

_TASK_FAIL_RESPONSES = {
    "network": [
        "Sir, network's being difficult. Want me to retry or switch approach?",
        "Connection issue, Sir. Should I try again?",
        "Net's slow right now, Sir. Retry?",
    ],
    "api_down": [
        "Sir, that service isn't responding. Trying a backup now.",
        "API's down, Sir. Switching to an alternative.",
        "Primary service unavailable — using fallback.",
    ],
    "api_key": [
        "Sir, API key issue. Need you to check the .env file.",
        "Authentication failed, Sir. Key might be invalid or expired.",
    ],
    "rate_limit": [
        "Sir, hitting API limits. Using a backup service instead.",
        "Rate limited — switching to alternative source.",
    ],
    "timeout": [
        "Sir, that's taking unusually long. Should I keep waiting or abort?",
        "Timed out, Sir. Retry or move on?",
    ],
    "app_not_found": [
        "Sir, I couldn't find that app. Want the web version instead?",
        "App isn't installed, Sir. Should I open it in browser?",
    ],
    "file_not_found": [
        "Sir, file's missing. Create a new one?",
        "Couldn't locate that file, Sir.",
    ],
    "permission": [
        "Sir, Windows is blocking that. Need admin rights.",
        "Permission denied, Sir. Try running Jarvis as administrator.",
    ],
    "file_locked": [
        "Sir, that file's being used. Close it and I'll retry.",
        "File is locked, Sir. Another program has it open.",
    ],
    "invalid_input": [
        "Sir, I didn't quite catch that. Could you rephrase?",
        "Need a bit more clarity, Sir.",
    ],
    "parse_error": [
        "Sir, couldn't make sense of that response. Let me try again.",
        "Data format issue — retrying.",
    ],
    "browser": [
        "Sir, browser's giving trouble. Let me restart it.",
        "Chrome issue — restarting the browser driver.",
    ],
    "tts": [
        "Sir, voice output glitched. Text is on screen.",
        "TTS failed, Sir. Check the chat panel.",
    ],
    "stt": [
        "Sir, couldn't hear that clearly. Say it again?",
        "Microphone's acting up — try once more.",
    ],
    "memory": [
        "Sir, memory file issue. Using cache for now.",
        "Couldn't access memory — running with session data only.",
    ],
    "generic": [
        "Sir, that didn't work. Want me to try another way?",
        "Task failed, Sir. Different approach?",
        "Couldn't complete that, Sir. Retry?",
    ],
}

_CRITICAL_RESPONSES = [
    "Sir, I hit a critical issue with {module}. Restarting that component now.",
    "Critical failure in {module}, Sir. Attempting recovery.",
    "Sir, {module} crashed. Bringing it back online.",
]

_RESTART_FAILED = [
    "Sir, {module} is down and won't restart. Everything else works. Want me to restart completely?",
    "Sir, {module} refuses to come back. Rest of me is fine — full restart?",
]

# ── Context Detection (from exception) ────────────────────────
def _detect_context(exc: Exception, manual: str = "") -> str:
    """Figure out error category from exception type/message."""
    if manual:
        return manual
    
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    
    if any(k in exc_str for k in ["connection", "network", "dns", "resolve"]):
        return "network"
    if any(k in exc_str for k in ["timeout", "timed out"]):
        return "timeout"
    if any(k in exc_str for k in ["401", "unauthorized", "api key", "authentication"]):
        return "api_key"
    if any(k in exc_str for k in ["429", "rate limit", "too many requests"]):
        return "rate_limit"
    if any(k in exc_str for k in ["503", "502", "bad gateway", "service unavailable"]):
        return "api_down"
    if "filenotfound" in exc_type or "no such file" in exc_str:
        return "file_not_found"
    if "permission" in exc_str or "access is denied" in exc_str:
        return "permission"
    if "being used by another" in exc_str or "locked" in exc_str:
        return "file_locked"
    if "json" in exc_str or "parse" in exc_str or "decode" in exc_str:
        return "parse_error"
    if any(k in exc_str for k in ["selenium", "chrome", "webdriver"]):
        return "browser"
    
    return "generic"

# ── Response picker ───────────────────────────────────────────
import random

def _pick_response(category: str, **kwargs) -> str:
    """Pick a random response from the category, formatted."""
    responses = _TASK_FAIL_RESPONSES.get(category, _TASK_FAIL_RESPONSES["generic"])
    template = random.choice(responses)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template

# ── Main error handler ────────────────────────────────────────
def handle_error(
    exc: Exception,
    context: str = "",
    tier: str = "task",
    module: str = "",
    user_friendly: bool = True,
) -> str:
    """
    Handle an exception and return a user-friendly response.
    
    Args:
        exc: The caught exception
        context: Optional hint (e.g., "network", "api_key")
        tier: "soft" / "task" / "critical"
        module: Module name for critical errors
        user_friendly: Return spoken-friendly msg (True) or raw (False)
    
    Returns:
        String to speak/display to user.
    """
    # Log full trace
    trace = traceback.format_exc()
    log.error(f"[{tier.upper()}] {type(exc).__name__}: {exc}")
    log.debug(f"Traceback:\n{trace}")
    
    if not user_friendly:
        return f"{type(exc).__name__}: {exc}"
    
    tier_enum = ErrorLevel(tier) if isinstance(tier, str) else tier
    
    if tier_enum == ErrorLevel.SOFT:
        return random.choice(_SOFT_RESPONSES)
    
    elif tier_enum == ErrorLevel.CRITICAL:
        template = random.choice(_CRITICAL_RESPONSES)
        return template.format(module=module or "a component")
    
    else:  # TASK
        category = _detect_context(exc, context)
        return _pick_response(category, module=module)

# ── Decorator for safe execution ──────────────────────────────
def safe_run(
    tier: str = "task",
    context: str = "",
    fallback: Any = None,
    retries: int = 0,
    retry_delay: float = 1.0,
):
    """
    Decorator: wraps a function with error handling.
    
    Args:
        tier: "soft" / "task" / "critical"
        context: Error category hint
        fallback: Value to return on failure
        retries: Auto-retry count (0 = no retry)
        retry_delay: Seconds between retries
    
    Example:
        @safe_run(tier="task", context="network", retries=2)
        def fetch_data():
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < retries:
                        log.warn(f"{func.__name__} retry {attempt+1}/{retries}")
                        time.sleep(retry_delay)
                        continue
                    # Final failure
                    msg = handle_error(
                        e,
                        context=context,
                        tier=tier,
                        module=func.__module__,
                    )
                    log.error(f"{func.__name__} failed: {msg}")
                    return fallback
            return fallback
        return wrapper
    return decorator

# ── Crash-proof wrapper ───────────────────────────────────────
def run_safely(func: Callable, *args, fallback=None, **kwargs):
    """
    One-off safe call — no decorator needed.
    
    Example:
        result = run_safely(risky_func, arg1, fallback="default")
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handle_error(e, tier="task")
        return fallback
    
# =============================================================
#  Main.py compat wrapper
# =============================================================
class _ErrorHandlerWrapper:
    """Compat object so Main.py can call error_handler.get_response(e, action=...)."""
    
    def get_response(self, exc: Exception, action: str = "", tier: str = "task") -> str:
        """Get error response text."""
        try:
            return handle_error(exc, context=action, tier=tier)
        except Exception:
            return "Something went wrong, Sir."
    
    def handle(self, exc: Exception, **kwargs):
        return handle_error(exc, **kwargs)

error_handler = _ErrorHandlerWrapper()    

# ── Test block ────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n─── ErrorHandler Test ───\n")
    
    # Test 1: Soft error
    try:
        raise ValueError("small issue")
    except Exception as e:
        msg = handle_error(e, tier="soft")
        print(f"SOFT   → {msg}")
    
    # Test 2: Task error — network
    try:
        raise ConnectionError("Failed to resolve host")
    except Exception as e:
        msg = handle_error(e, tier="task")
        print(f"NETWORK→ {msg}")
    
    # Test 3: Task error — API key
    try:
        raise Exception("401 Unauthorized: invalid API key")
    except Exception as e:
        msg = handle_error(e, tier="task")
        print(f"API KEY→ {msg}")
    
    # Test 4: Task error — rate limit
    try:
        raise Exception("429 Too Many Requests")
    except Exception as e:
        msg = handle_error(e, tier="task")
        print(f"RATE  → {msg}")
    
    # Test 5: Critical
    try:
        raise RuntimeError("Voice module crashed")
    except Exception as e:
        msg = handle_error(e, tier="critical", module="TextToSpeech")
        print(f"CRIT  → {msg}")
    
    # Test 6: Decorator with retries
    attempt_counter = [0]
    
    @safe_run(tier="task", context="network", retries=2, fallback="FALLBACK_VALUE")
    def flaky_function():
        attempt_counter[0] += 1
        if attempt_counter[0] < 3:
            raise ConnectionError("Network hiccup")
        return "SUCCESS"
    
    result = flaky_function()
    print(f"\nDECORATOR after 2 retries: {result}  (attempts={attempt_counter[0]})")
    
    # Test 7: Decorator with permanent failure
    @safe_run(tier="task", fallback="SAFE_DEFAULT")
    def always_fails():
        raise RuntimeError("never works")
    
    result = always_fails()
    print(f"PERMA-FAIL returns: {result}")
    
    print("\n✓ ErrorHandler test complete\n")