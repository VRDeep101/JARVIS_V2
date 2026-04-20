# =============================================================
#  Backend/Automation/AppRegistry.py - Unified App Launcher
#
#  Kya karta:
#    - Apps ko desktop priority se open karta
#    - Desktop nahi mila -> web version open (Chrome)
#    - Popular apps ka direct web link registered
#    - Chrome profile smart picker (Deep vs Risky vs JarvisAI)
#    - Close apps via pyautogui / psutil
#    - Fuzzy match ("vscode" / "vs code" / "visual studio" -> same)
#
#  App priority order:
#    1. Registered desktop path (PathResolver)
#    2. AppOpener library
#    3. Web fallback (Chrome with URL)
#
#  Usage:
#    from Backend.Automation.AppRegistry import app_registry
#    app_registry.open("chrome")
#    app_registry.open("instagram")  # no desktop -> opens web
#    app_registry.close("whatsapp")
# =============================================================

import os
import subprocess
import time
import webbrowser
from typing import Optional, Dict, List
from pathlib import Path

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Core.ErrorHandler import safe_run

log = get_logger("AppRegistry")

# -- Optional deps --------------------------------------------
try:
    from AppOpener import open as appopener_open, close as appopener_close
    APPOPENER_OK = True
except ImportError:
    APPOPENER_OK = False
    log.warn("AppOpener not installed")

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    import pyautogui
    PYAUTOGUI_OK = True
except ImportError:
    PYAUTOGUI_OK = False

# =============================================================
#  APP REGISTRY - Central mapping
#
#  Each entry: name -> {
#    desktop: app key for PathResolver OR direct path,
#    web:     URL to open in browser if no desktop,
#    alt_names: list of alternate voice commands,
#    process_name: name to match for close (psutil),
#  }
# =============================================================
APP_REGISTRY: Dict[str, Dict] = {
    # -- Browsers --
    "chrome": {
        "desktop": "chrome",
        "web": None,
        "alt_names": ["google chrome", "chrome browser"],
        "process_name": "chrome.exe",
    },
    "firefox": {
        "desktop": None,  # Try AppOpener
        "web": None,
        "alt_names": ["mozilla", "mozilla firefox"],
        "process_name": "firefox.exe",
    },
    "edge": {
        "desktop": None,
        "web": None,
        "alt_names": ["microsoft edge", "msedge"],
        "process_name": "msedge.exe",
    },
    
    # -- Dev tools --
    "vscode": {
        "desktop": "vscode",
        "web": None,
        "alt_names": ["vs code", "visual studio code", "code"],
        "process_name": "Code.exe",
    },
    
    # -- Social / Messaging --
    "whatsapp": {
        "desktop": "whatsapp",
        "web": "https://web.whatsapp.com",
        "alt_names": ["whats app"],
        "process_name": "WhatsApp.exe",
    },
    "telegram": {
        "desktop": "telegram",
        "web": "https://web.telegram.org",
        "alt_names": ["tg"],
        "process_name": "Telegram.exe",
    },
    "discord": {
        "desktop": "discord",
        "web": "https://discord.com/app",
        "alt_names": [],
        "process_name": "Discord.exe",
    },
    "slack": {
        "desktop": None,
        "web": "https://slack.com",
        "alt_names": [],
        "process_name": "slack.exe",
    },
    
    # -- Media --
    "spotify": {
        "desktop": "spotify",
        "web": "https://open.spotify.com",
        "alt_names": [],
        "process_name": "Spotify.exe",
    },
    "youtube": {
        "desktop": None,
        "web": "https://youtube.com",
        "alt_names": ["yt"],
        "process_name": None,
    },
    "youtube music": {
        "desktop": None,
        "web": "https://music.youtube.com",
        "alt_names": ["yt music"],
        "process_name": None,
    },
    
    # -- Social apps (web only) --
    "instagram": {
        "desktop": None,
        "web": "https://instagram.com",
        "alt_names": ["insta", "ig"],
        "process_name": None,
    },
    "facebook": {
        "desktop": None,
        "web": "https://facebook.com",
        "alt_names": ["fb"],
        "process_name": None,
    },
    "twitter": {
        "desktop": None,
        "web": "https://twitter.com",
        "alt_names": ["x", "x.com"],
        "process_name": None,
    },
    "linkedin": {
        "desktop": None,
        "web": "https://linkedin.com",
        "alt_names": [],
        "process_name": None,
    },
    "reddit": {
        "desktop": None,
        "web": "https://reddit.com",
        "alt_names": [],
        "process_name": None,
    },
    
    # -- Mail --
    "gmail": {
        "desktop": None,
        "web": "https://mail.google.com",
        "alt_names": ["mail", "email"],
        "process_name": None,
    },
    "outlook": {
        "desktop": None,
        "web": "https://outlook.live.com",
        "alt_names": [],
        "process_name": "outlook.exe",
    },
    
    # -- Utilities (Windows built-in) --
    "notepad": {
        "desktop": "notepad",
        "web": None,
        "alt_names": [],
        "process_name": "notepad.exe",
    },
    "calculator": {
        "desktop": None,
        "web": None,
        "alt_names": ["calc"],
        "process_name": "CalculatorApp.exe",
    },
    "explorer": {
        "desktop": "explorer",
        "web": None,
        "alt_names": ["file explorer", "files", "this pc"],
        "process_name": "explorer.exe",
    },
    "settings": {
        "desktop": None,
        "web": None,
        "alt_names": ["windows settings"],
        "process_name": None,  # special handling
    },
    "cmd": {
        "desktop": "cmd",
        "web": None,
        "alt_names": ["command prompt", "terminal"],
        "process_name": "cmd.exe",
    },
    "task manager": {
        "desktop": None,
        "web": None,
        "alt_names": ["taskmgr"],
        "process_name": "Taskmgr.exe",
    },
    
    # -- AI services (web) --
    "chatgpt": {
        "desktop": None,
        "web": "https://chatgpt.com",
        "alt_names": ["chat gpt", "gpt"],
        "process_name": None,
    },
    "claude": {
        "desktop": None,
        "web": "https://claude.ai",
        "alt_names": ["claude ai"],
        "process_name": None,
    },
    "gemini": {
        "desktop": None,
        "web": "https://gemini.google.com",
        "alt_names": ["bard"],
        "process_name": None,
    },
    
    # -- Google suite --
    "google": {
        "desktop": None,
        "web": "https://google.com",
        "alt_names": [],
        "process_name": None,
    },
    "google drive": {
        "desktop": None,
        "web": "https://drive.google.com",
        "alt_names": ["drive", "gdrive"],
        "process_name": None,
    },
    "google docs": {
        "desktop": None,
        "web": "https://docs.google.com",
        "alt_names": ["docs"],
        "process_name": None,
    },
}

# =============================================================
#  Helper: resolve app name from voice input
# =============================================================
def _resolve_app_name(query: str) -> Optional[str]:
    """
    Find canonical app name from user input.
    Tries exact match, then alt_names, then fuzzy substring.
    """
    q = query.lower().strip()
    
    # Exact match
    if q in APP_REGISTRY:
        return q
    
    # Alt names
    for name, data in APP_REGISTRY.items():
        if q in [alt.lower() for alt in data.get("alt_names", [])]:
            return name
    
    # Substring match (partial)
    for name in APP_REGISTRY:
        if q in name or name in q:
            return name
    
    # Alt substring
    for name, data in APP_REGISTRY.items():
        for alt in data.get("alt_names", []):
            if q in alt.lower() or alt.lower() in q:
                return name
    
    return None

# =============================================================
#  Chrome profile picker (for web fallback)
# =============================================================
def _pick_chrome_profile() -> Optional[str]:
    """
    Pick best Chrome profile for web fallback.
    Priority: recently used > Deep > Risky > JarvisAI > Default
    
    Returns profile folder name or None.
    """
    profiles = paths.chrome_profile_names()
    if not profiles:
        return None
    
    # Profile priority by display name
    priority_display = ["deep", "risky", "default", "jarvisai"]
    
    # Try to match by display name
    for pref in priority_display:
        for folder, display in profiles.items():
            if display.lower() == pref or pref in display.lower():
                return folder
    
    # Fallback: first profile
    return next(iter(profiles.keys()))

def _chrome_cmd_with_profile(url: str, profile: Optional[str] = None) -> List[str]:
    """Build Chrome command to open URL in specific profile."""
    chrome_path = paths.find_app("chrome")
    if not chrome_path:
        return []
    
    cmd = [chrome_path, "--new-window"]
    if profile:
        cmd.append(f"--profile-directory={profile}")
    cmd.append(url)
    return cmd

# =============================================================
#  AppRegistry class
# =============================================================
class AppRegistry:
    """Unified app launcher."""
    
    def open(self, app_query: str, prefer_desktop: bool = True) -> Dict:
        """
        Open an app.
        Returns: {"ok": bool, "method": str, "message": str}
        
        method: "desktop" / "appopener" / "web" / "failed"
        """
        if not app_query:
            return {"ok": False, "method": "failed", "message": "No app name given"}
        
        resolved = _resolve_app_name(app_query)
        
        # If not in registry, try AppOpener anyway (user might know the app)
        if not resolved:
            return self._open_unknown(app_query)
        
        cfg = APP_REGISTRY[resolved]
        
        # -- Special: Settings app ---------------------------
        if resolved == "settings":
            return self._open_settings()
        
        # -- Try desktop first --------------------------------
        if prefer_desktop and cfg.get("desktop"):
            result = self._open_desktop(resolved, cfg)
            if result["ok"]:
                return result
        
        # -- AppOpener fallback (tries registered Windows apps) --
        if prefer_desktop and APPOPENER_OK:
            result = self._open_via_appopener(resolved)
            if result["ok"]:
                return result
        
        # -- Web fallback -------------------------------------
        if cfg.get("web"):
            return self._open_web(cfg["web"], app_name=resolved)
        
        return {
            "ok": False,
            "method": "failed",
            "message": f"Couldn't open {resolved}, Sir. No desktop app or web version available.",
        }
    
    def _open_desktop(self, name: str, cfg: Dict) -> Dict:
        """Try launching desktop version."""
        desktop_key = cfg["desktop"]
        
        # PathResolver lookup
        path = paths.find_app(desktop_key)
        if not path:
            return {"ok": False, "method": "failed", "message": "not found"}
        
        try:
            subprocess.Popen([path], shell=False)
            log.action(f"Opened desktop: {name} ({path})")
            return {
                "ok": True,
                "method": "desktop",
                "message": f"Opened {name}, Sir.",
            }
        except Exception as e:
            log.error(f"Desktop open error for {name}: {e}")
            return {"ok": False, "method": "failed", "message": str(e)}
    
    def _open_via_appopener(self, name: str) -> Dict:
        """Use AppOpener library."""
        if not APPOPENER_OK:
            return {"ok": False, "method": "failed", "message": "AppOpener missing"}
        try:
            appopener_open(name, match_closest=True, output=False, throw_error=True)
            log.action(f"Opened via AppOpener: {name}")
            return {
                "ok": True,
                "method": "appopener",
                "message": f"Opened {name}, Sir.",
            }
        except Exception as e:
            log.debug(f"AppOpener failed for {name}: {e}")
            return {"ok": False, "method": "failed", "message": str(e)}
    
    def _open_web(self, url: str, app_name: str = "") -> Dict:
        """Open URL in Chrome with picked profile."""
        profile = _pick_chrome_profile()
        cmd = _chrome_cmd_with_profile(url, profile)
        
        try:
            if cmd:
                subprocess.Popen(cmd, shell=False)
                msg = f"Opening {app_name or 'that'} in Chrome"
                if profile:
                    display = paths.chrome_profile_names().get(profile, profile)
                    msg += f" ({display} profile)"
                msg += ", Sir."
            else:
                # Fallback to default browser
                webbrowser.open(url)
                msg = f"Opening {app_name or 'that'} in browser, Sir."
            
            log.action(f"Opened web: {url}")
            return {"ok": True, "method": "web", "message": msg}
        except Exception as e:
            log.error(f"Web open error: {e}")
            return {"ok": False, "method": "failed", "message": str(e)}
    
    def _open_settings(self) -> Dict:
        """Windows Settings app."""
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:"], shell=False)
            log.action("Opened Windows Settings")
            return {"ok": True, "method": "desktop", "message": "Opening Settings, Sir."}
        except Exception as e:
            return {"ok": False, "method": "failed", "message": str(e)}
    
    def _open_unknown(self, app_query: str) -> Dict:
        """App not in our registry - try AppOpener as last resort."""
        if not APPOPENER_OK:
            return {
                "ok": False,
                "method": "failed",
                "message": f"I don't know how to open '{app_query}', Sir.",
            }
        try:
            appopener_open(app_query, match_closest=True, output=False, throw_error=True)
            log.action(f"Opened unknown app: {app_query}")
            return {
                "ok": True,
                "method": "appopener",
                "message": f"Opened {app_query}, Sir.",
            }
        except Exception as e:
            return {
                "ok": False,
                "method": "failed",
                "message": f"Couldn't find {app_query}, Sir.",
            }
    
    # =========================================================
    #  CLOSE
    # =========================================================
    def close(self, app_query: str) -> Dict:
        """Close an app."""
        if not app_query:
            return {"ok": False, "message": "No app given"}
        
        resolved = _resolve_app_name(app_query)
        if not resolved:
            # Try AppOpener close directly
            return self._close_via_appopener(app_query)
        
        cfg = APP_REGISTRY[resolved]
        
        # Try psutil first (most reliable)
        if cfg.get("process_name") and PSUTIL_OK:
            result = self._close_via_psutil(resolved, cfg["process_name"])
            if result["ok"]:
                return result
        
        # AppOpener fallback
        return self._close_via_appopener(resolved)
    
    def _close_via_psutil(self, name: str, process_name: str) -> Dict:
        """Terminate by process name."""
        if not PSUTIL_OK:
            return {"ok": False, "message": "psutil missing"}
        
        killed = 0
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                        proc.terminate()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if killed > 0:
                log.action(f"Closed {name} ({killed} process{'es' if killed > 1 else ''})")
                return {"ok": True, "message": f"Closed {name}, Sir."}
            else:
                return {"ok": False, "message": f"{name} wasn't running, Sir."}
        except Exception as e:
            log.error(f"psutil close error: {e}")
            return {"ok": False, "message": str(e)}
    
    def _close_via_appopener(self, name: str) -> Dict:
        """Use AppOpener close."""
        if not APPOPENER_OK:
            return {"ok": False, "message": f"Can't close {name}, Sir."}
        try:
            appopener_close(name, match_closest=True, output=False, throw_error=True)
            log.action(f"Closed via AppOpener: {name}")
            return {"ok": True, "message": f"Closed {name}, Sir."}
        except Exception as e:
            log.debug(f"AppOpener close error: {e}")
            return {"ok": False, "message": f"Couldn't close {name}, Sir."}
    
    # =========================================================
    #  LIST / STATUS
    # =========================================================
    def list_apps(self) -> List[str]:
        """All registered app names."""
        return sorted(APP_REGISTRY.keys())
    
    def is_running(self, app_query: str) -> bool:
        """Check if app is running."""
        if not PSUTIL_OK:
            return False
        resolved = _resolve_app_name(app_query)
        if not resolved:
            return False
        proc_name = APP_REGISTRY[resolved].get("process_name")
        if not proc_name:
            return False
        
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == proc_name.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

# =============================================================
#  Singleton
# =============================================================
app_registry = AppRegistry()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- AppRegistry Test ---\n")
    
    print(f"Registered apps ({len(app_registry.list_apps())}):")
    for a in app_registry.list_apps():
        print(f"  - {a}")
    
    print("\n-- Name Resolution --")
    test_names = [
        "vs code", "vscode", "code",
        "whats app", "whatsapp", "wa",
        "instagram", "insta", "ig",
        "chatgpt", "chat gpt", "gpt",
        "nonexistent app xyz",
    ]
    for t in test_names:
        resolved = _resolve_app_name(t)
        print(f"  '{t:25}' -> {resolved}")
    
    print("\n-- Chrome Profile Picker --")
    picked = _pick_chrome_profile()
    profiles = paths.chrome_profile_names()
    print(f"  Available: {profiles}")
    print(f"  Picked   : {picked}")
    
    print("\n-- Running Status --")
    for app in ["chrome", "vscode", "whatsapp"]:
        running = app_registry.is_running(app)
        print(f"  {app:15} running: {running}")
    
    # Don't actually open apps in test (too disruptive)
    # Uncomment to live-test:
    # print("\n-- Live Test: Open notepad --")
    # r = app_registry.open("notepad")
    # print(f"  Result: {r}")
    # time.sleep(2)
    # print("-- Live Test: Close notepad --")
    # r = app_registry.close("notepad")
    # print(f"  Result: {r}")
    
    print("\n[OK] AppRegistry test complete\n")