# =============================================================
#  Backend/Modes/SecurityMode.py - Threat Monitoring
#
#  Kya karta:
#    - Clipboard monitor (every 3 sec, checks URLs)
#    - Phishing detection on copied/spoken URLs
#    - HaveIBeenPwned API - email breach check (FREE)
#    - Suspicious download alert (watches Downloads folder)
#    - Password strength analyzer
#    - Background thread - starts on mode enter, stops on exit
#
#  Uses PhishingDetector (Phase 7 builds full version).
#  Here: basic URL risk scoring + real-time monitoring.
#
#  Usage:
#    from Backend.Modes.SecurityMode import security_mode
#    security_mode.enter(on_speak=tts_cb)
#    security_mode.check_url("paypal.com")
#    security_mode.check_password("mypass123")
# =============================================================
from __future__ import annotations  

import hashlib
import re
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Optional

import requests

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Utils.InternetCheck import net
from Backend.Core.ModeManager import mode_manager, Mode
from Backend.Core.ErrorHandler import safe_run

log = get_logger("SecurityMode")

# -- Optional deps --------------------------------------------
try:
    import pyperclip
    PYPERCLIP_OK = True
except ImportError:
    PYPERCLIP_OK = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_OK = True
except ImportError:
    WATCHDOG_OK = False

# =============================================================
#  CONFIG
# =============================================================
CLIPBOARD_CHECK_INTERVAL = 3  # seconds
SUSPICIOUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".scr", ".vbs", ".ps1", ".msi", ".dll"}

# Known phishing patterns (basic - PhishingDetector will expand)
PHISHING_PATTERNS = [
    r"paypal.*\.(?!com/)",           # paypal-something.xyz
    r"amaz[o0]n.*\.(?!com|in|co)",   # amazon lookalikes
    r".*verify.*account.*",
    r".*urgent.*click.*",
    r".*g00gle",
    r".*faceb00k",
    r"bit\.ly|tinyurl\.com|goo\.gl|t\.co",  # shorteners = suspicious
    r".*\.tk|\.ml|\.ga|\.cf|\.gq",   # free sketchy TLDs
]

URL_REGEX = re.compile(
    r'\b(?:https?://)?(?:[a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
)

# =============================================================
#  SecurityMode class
# =============================================================
class SecurityMode:
    """Active threat monitoring."""
    
    def __init__(self):
        self.active = False
        self.on_speak: Optional[Callable] = None
        
        # Clipboard monitor
        self._last_clipboard = ""
        self._clipboard_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Download watcher — string literal avoids Pylance error
        # when watchdog is not installed (WATCHDOG_OK = False)
        self._download_observer: Optional["Observer"] = None
    
    # =========================================================
    #  Enter / Exit
    # =========================================================
    def enter(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        """Activate Security mode."""
        self.active = True
        self.on_speak = on_speak
        self._stop_event.clear()
        
        info = mode_manager.current_info
        announce = info["voice_announce"]
        log.info("Security mode entered")
        
        if on_speak:
            on_speak(announce)
        
        # Start background monitors
        self._start_clipboard_monitor()
        self._start_download_watcher()
        
        return announce
    
    def exit(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        """Deactivate Security mode - stop all monitors."""
        self.active = False
        self._stop_event.set()
        
        # Stop clipboard monitor
        if self._clipboard_thread and self._clipboard_thread.is_alive():
            self._clipboard_thread.join(timeout=2)
        
        # Stop download watcher
        if self._download_observer:
            try:
                self._download_observer.stop()
                self._download_observer.join(timeout=2)
            except Exception:
                pass
            self._download_observer = None
        
        log.info("Security mode exited")
        msg = "Security mode deactivated, Sir."
        if on_speak:
            on_speak(msg)
        return msg
    
    def is_active(self) -> bool:
        return self.active and mode_manager.current_mode == Mode.SECURITY
    
    # =========================================================
    #  CLIPBOARD MONITOR
    # =========================================================
    def _start_clipboard_monitor(self):
        """Start background thread watching clipboard."""
        if not PYPERCLIP_OK:
            log.warn("pyperclip missing - clipboard monitor disabled")
            return
        
        self._clipboard_thread = threading.Thread(
            target=self._clipboard_loop,
            daemon=True,
            name="SecClipboard",
        )
        self._clipboard_thread.start()
        log.info("Clipboard monitor started")
    
    def _clipboard_loop(self):
        """Check clipboard every N seconds for suspicious URLs."""
        while not self._stop_event.is_set():
            try:
                current = pyperclip.paste()
                if current and current != self._last_clipboard:
                    self._last_clipboard = current
                    # Extract URLs
                    urls = URL_REGEX.findall(current)
                    for url in urls[:2]:  # check max 2 per clipboard event
                        if self._is_suspicious_url(url):
                            self._alert(f"Sir, suspicious link copied: {url[:50]}. Verify before opening.")
            except Exception as e:
                log.debug(f"Clipboard loop error: {e}")
            
            # Wait (but wake fast on stop)
            for _ in range(CLIPBOARD_CHECK_INTERVAL * 2):
                if self._stop_event.is_set():
                    return
                time.sleep(0.5)
    
    # =========================================================
    #  URL CHECKING
    # =========================================================
    def _is_suspicious_url(self, url: str) -> bool:
        """Quick local phishing pattern check."""
        if not url:
            return False
        url_lower = url.lower()
        for pattern in PHISHING_PATTERNS:
            if re.search(pattern, url_lower):
                return True
        return False
    
    def check_url(self, url: str) -> Dict:
        """
        Full URL analysis.
        Returns risk score + reasons + verdict.
        """
        if not url:
            return {"safe": True, "risk_score": 0, "reasons": [], "verdict": "Empty URL"}
        
        # Normalize
        url = url.strip().lower()
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        
        risk = 0
        reasons = []
        
        # HTTP (not HTTPS)
        if url.startswith("http://"):
            risk += 20
            reasons.append("No HTTPS encryption")
        
        # Suspicious patterns
        for pattern in PHISHING_PATTERNS:
            if re.search(pattern, url):
                risk += 30
                reasons.append(f"Matches phishing pattern")
                break
        
        # Excessive subdomains
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.netloc
            subdomain_count = host.count(".")
            if subdomain_count > 3:
                risk += 20
                reasons.append(f"Too many subdomains ({subdomain_count})")
            
            # IP address as domain
            if re.match(r"^\d+\.\d+\.\d+\.\d+", host):
                risk += 40
                reasons.append("Uses IP address instead of domain")
            
            # Very long URL
            if len(url) > 150:
                risk += 15
                reasons.append("Unusually long URL")
            
            # Suspicious keywords in URL
            sus_keywords = ["verify", "suspend", "urgent", "click-here", "login-"]
            for kw in sus_keywords:
                if kw in url:
                    risk += 15
                    reasons.append(f"Contains suspicious keyword: {kw}")
                    break
        except Exception:
            pass
        
        # Verdict
        risk = min(100, risk)
        safe = risk < 40
        
        if risk < 30:
            verdict = "Looks safe, Sir."
        elif risk < 60:
            verdict = "Suspicious - proceed with caution, Sir."
        elif risk < 80:
            verdict = "HIGH RISK - do not click, Sir."
        else:
            verdict = "DANGER - this is almost certainly malicious, Sir."
        
        return {
            "url": url,
            "safe": safe,
            "risk_score": risk,
            "reasons": reasons,
            "verdict": verdict,
        }
    
    # =========================================================
    #  EMAIL BREACH CHECK (HaveIBeenPwned - free API)
    # =========================================================
    def check_email_breach(self, email: str) -> Dict:
        """Check if email appeared in any known data breach."""
        if not net.is_online():
            return {"ok": False, "message": "Offline, Sir. Can't check breaches."}
        
        try:
            # HIBP requires API key for email search (paid)
            # Free alternative: check password hash endpoint
            # For email, we'll use the k-anonymity approach
            # Actually: for educational purposes, noting this needs paid API
            return {
                "ok": False,
                "message": "Email breach check requires paid HIBP API key, Sir. Use passwords check instead.",
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def check_password(self, password: str) -> Dict:
        """
        Check if password appeared in known breaches (FREE, safe).
        Uses HIBP k-anonymity - only first 5 chars of hash sent.
        """
        if not password:
            return {"ok": False, "message": "Need a password to check, Sir."}
        
        if not net.is_online():
            return {"ok": False, "message": "Offline, Sir."}
        
        try:
            # SHA-1 hash of password
            hashed = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
            prefix = hashed[:5]
            suffix = hashed[5:]
            
            # Query HIBP's k-anonymity API
            url = f"https://api.pwnedpasswords.com/range/{prefix}"
            response = requests.get(url, timeout=8)
            
            if response.status_code != 200:
                return {"ok": False, "message": "HIBP API unavailable, Sir."}
            
            # Check if our suffix is in the response
            for line in response.text.splitlines():
                if ":" in line:
                    h, count = line.split(":", 1)
                    if h.strip() == suffix:
                        count = int(count.strip())
                        return {
                            "ok": True,
                            "breached": True,
                            "count": count,
                            "message": (
                                f"Sir, this password has been seen in {count:,} data breaches. "
                                f"Change it immediately."
                            ),
                        }
            
            # Not found
            return {
                "ok": True,
                "breached": False,
                "count": 0,
                "message": "Password not found in known breaches, Sir. Still, use a unique one.",
            }
        except Exception as e:
            log.error(f"HIBP check error: {e}")
            return {"ok": False, "message": f"Check failed: {str(e)[:60]}"}
    
    def password_strength(self, password: str) -> Dict:
        """Analyze password strength locally (no network)."""
        if not password:
            return {"strength": "empty", "score": 0, "issues": ["No password"]}
        
        score = 0
        issues = []
        
        # Length
        if len(password) < 8:
            issues.append("Too short (< 8 chars)")
        elif len(password) >= 12:
            score += 25
        else:
            score += 10
        
        # Character variety
        has_lower = bool(re.search(r"[a-z]", password))
        has_upper = bool(re.search(r"[A-Z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_special = bool(re.search(r"[^a-zA-Z\d]", password))
        
        variety = sum([has_lower, has_upper, has_digit, has_special])
        score += variety * 15
        
        if not has_upper:
            issues.append("No uppercase")
        if not has_lower:
            issues.append("No lowercase")
        if not has_digit:
            issues.append("No digits")
        if not has_special:
            issues.append("No special chars")
        
        # Common patterns
        common_patterns = ["123", "abc", "password", "qwerty", "admin", "1406"]
        for p in common_patterns:
            if p in password.lower():
                score -= 20
                issues.append(f"Contains common pattern: {p}")
                break
        
        score = max(0, min(100, score))
        
        if score < 30:
            strength = "weak"
        elif score < 60:
            strength = "fair"
        elif score < 85:
            strength = "strong"
        else:
            strength = "excellent"
        
        return {
            "strength": strength,
            "score": score,
            "issues": issues,
        }
    
    # =========================================================
    #  DOWNLOAD WATCHER
    # =========================================================
    def _start_download_watcher(self):
        """Watch Downloads folder for suspicious files."""
        if not WATCHDOG_OK:
            return
        
        downloads = paths.DOWNLOADS_DIR
        if not downloads.exists():
            return
        
        class Handler(FileSystemEventHandler):
            def __init__(self, parent):
                self.parent = parent
            
            def on_created(self, event):
                if event.is_directory:
                    return
                ext = Path(event.src_path).suffix.lower()
                if ext in SUSPICIOUS_EXTENSIONS:
                    name = Path(event.src_path).name
                    self.parent._alert(
                        f"Sir, suspicious file downloaded: {name}. Verify before running."
                    )
        
        try:
            observer = Observer()
            observer.schedule(Handler(self), str(downloads), recursive=False)
            observer.start()
            self._download_observer = observer
            log.info(f"Download watcher started: {downloads}")
        except Exception as e:
            log.debug(f"Download watcher error: {e}")
    
    # =========================================================
    #  ALERT
    # =========================================================
    def _alert(self, message: str):
        """Speak + log a security alert."""
        log.warn(f"SECURITY ALERT: {message}")
        if self.on_speak:
            try:
                self.on_speak(message)
            except Exception as e:
                log.error(f"Alert speak error: {e}")

# =============================================================
#  Singleton
# =============================================================
security_mode = SecurityMode()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- SecurityMode Test ---\n")
    
    # URL analysis (no network needed)
    print("-- URL Risk Check --")
    test_urls = [
        "https://google.com",
        "http://paypal-verify-account.tk",
        "https://192.168.1.1/login",
        "https://bit.ly/xyz123",
        "https://bankofamerica.com",
    ]
    for url in test_urls:
        r = security_mode.check_url(url)
        icon = "[SAFE]" if r["safe"] else "[RISK]"
        print(f"  {icon} {url}")
        print(f"         risk={r['risk_score']}  {r['verdict']}")
        if r["reasons"]:
            print(f"         reasons: {', '.join(r['reasons'][:3])}")
        print()
    
    # Password strength
    print("-- Password Strength --")
    test_passwords = [
        "123456",
        "password",
        "MyP@ss2024",
        "X9!kLm2$qP#4Zn",
    ]
    for p in test_passwords:
        r = security_mode.password_strength(p)
        print(f"  '{p:<20}' -> {r['strength']:10} (score: {r['score']})")
        if r["issues"]:
            print(f"    issues: {', '.join(r['issues'][:3])}")
    
    # HIBP check (needs internet)
    print("\n-- Breach Check (requires internet) --")
    if net.is_online():
        r = security_mode.check_password("password123")
        print(f"  'password123': {r.get('message', '')}")
    else:
        print("  Offline - skipped")
    
    print("\n[OK] SecurityMode test complete\n")