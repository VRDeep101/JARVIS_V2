# ═════════════════════════════════════════════════════════════
#  Backend/Utils/Logger.py  —  Central Logging System
#
#  Kya karta:
#    - Saara events log karta (Logs/jarvis.log)
#    - Errors alag file me (Logs/errors.log)
#    - Self-edits track karta (Logs/self_edits.log)
#    - Terminal pe colored output deta
#    - Auto log rotation (file > 5 MB → archive)
#
#  Usage:
#    from Backend.Utils.Logger import log
#    log.info("Jarvis started")
#    log.error("API timeout")
#    log.success("Task complete")
# ═════════════════════════════════════════════════════════════

import os
import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

# ── Paths ─────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.parent.absolute()
LOGS_DIR = BASE_DIR / "Logs"
LOGS_DIR.mkdir(exist_ok=True)

MAIN_LOG  = LOGS_DIR / "jarvis.log"
ERROR_LOG = LOGS_DIR / "errors.log"
SELFEDIT_LOG = LOGS_DIR / "self_edits.log"

# ── Terminal Colors ───────────────────────────────────────────
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    GRAY    = "\033[90m"

# ── File Formatter (plain text) ───────────────────────────────
_file_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ── Main File Handler (5 MB rotation, keep 3 backups) ─────────
_main_handler = RotatingFileHandler(
    MAIN_LOG, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_main_handler.setFormatter(_file_formatter)
_main_handler.setLevel(logging.INFO)

# ── Error File Handler (only errors+) ─────────────────────────
_error_handler = RotatingFileHandler(
    ERROR_LOG, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
)
_error_handler.setFormatter(_file_formatter)
_error_handler.setLevel(logging.ERROR)

# ── Logger Factory ────────────────────────────────────────────
_loggers: dict = {}

def _get_logger(name: str) -> logging.Logger:
    """Returns a configured logger for the given module name."""
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    if not logger.handlers:
        logger.addHandler(_main_handler)
        logger.addHandler(_error_handler)
    
    _loggers[name] = logger
    return logger

# ── Public Log Interface ──────────────────────────────────────
class JarvisLogger:
    """
    Centralized logger with colored terminal output + file logging.
    
    Usage:
        from Backend.Utils.Logger import log
        log.info("System started")
        log.success("Task complete")
        log.warn("API slow")
        log.error("Connection failed")
        log.debug("Internal state: ...")
    """
    
    def __init__(self, name: str = "Jarvis"):
        self.name = name
        self._logger = _get_logger(name)
    
    def _terminal_output(self, level: str, msg: str, color: str = ""):
        """Print to terminal with color and timestamp."""
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {
            "INFO":    "ℹ",
            "SUCCESS": "✓",
            "WARN":    "⚠",
            "ERROR":   "✗",
            "DEBUG":   "›",
            "ACTION":  "▶",
            "VOICE":   "🔊",
            "LISTEN":  "🎤",
        }
        icon = icons.get(level, "•")
        module = f"{Color.GRAY}[{self.name}]{Color.RESET}"
        print(f"{Color.DIM}{ts}{Color.RESET} {module} {color}{icon} {msg}{Color.RESET}")
    
    def info(self, msg: str):
        self._logger.info(msg)
        self._terminal_output("INFO", msg, Color.CYAN)
    
    def success(self, msg: str):
        self._logger.info(f"[SUCCESS] {msg}")
        self._terminal_output("SUCCESS", msg, Color.GREEN)
    
    def warn(self, msg: str):
        self._logger.warning(msg)
        self._terminal_output("WARN", msg, Color.YELLOW)
    
    def error(self, msg: str, exc_info: bool = False):
        self._logger.error(msg, exc_info=exc_info)
        self._terminal_output("ERROR", msg, Color.RED)
    
    def debug(self, msg: str):
        self._logger.debug(msg)
        # Debug only in terminal if env flag set
        if os.environ.get("JARVIS_DEBUG") == "1":
            self._terminal_output("DEBUG", msg, Color.GRAY)
    
    def action(self, msg: str):
        """For actions Jarvis is taking (e.g., 'Opening Chrome...')"""
        self._logger.info(f"[ACTION] {msg}")
        self._terminal_output("ACTION", msg, Color.BLUE)
    
    def voice(self, msg: str):
        """For voice output events."""
        self._logger.info(f"[VOICE] {msg}")
        self._terminal_output("VOICE", msg, Color.MAGENTA)
    
    def listen(self, msg: str):
        """For voice input events."""
        self._logger.info(f"[LISTEN] {msg}")
        self._terminal_output("LISTEN", msg, Color.MAGENTA)
    
    def self_edit(self, file: str, change: str):
        """Logs self-adaptation events separately."""
        entry = f"{datetime.now().isoformat()} | {file} | {change}\n"
        try:
            with open(SELFEDIT_LOG, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
        self._logger.info(f"[SELF-EDIT] {file} — {change}")
        self._terminal_output("ACTION", f"Self-edit: {file} — {change}", Color.MAGENTA)

# ── Default logger instance ───────────────────────────────────
log = JarvisLogger("Jarvis")

def get_logger(name: str) -> JarvisLogger:
    """Get a module-specific logger."""
    return JarvisLogger(name)

# ── Test block ────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n─── Logger Test ───\n")
    log.info("Jarvis starting up...")
    log.success("Memory loaded successfully")
    log.action("Opening Chrome")
    log.voice("Speaking: Welcome back, Sir")
    log.listen("Hearing: what's the weather")
    log.warn("API response slow")
    log.error("Connection timeout after 30s")
    log.debug("Internal queue size: 3")
    log.self_edit("Backend/Voice/SpeechToText.py", "Added 'harvis' to corrections")
    
    # Test module-specific logger
    mod_log = get_logger("Chatbot")
    mod_log.info("Chatbot module initialized")
    mod_log.success("Groq connection OK")
    
    print(f"\n{Color.GREEN}✓ Logger test complete{Color.RESET}")
    print(f"{Color.DIM}Check: {MAIN_LOG}{Color.RESET}")
    print(f"{Color.DIM}Check: {ERROR_LOG}{Color.RESET}\n")