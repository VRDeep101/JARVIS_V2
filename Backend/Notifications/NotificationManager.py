# =============================================================
#  Backend/Notifications/NotificationManager.py
#
#  Kya karta:
#    - Notifications log rakhta (Data/notifications.json)
#    - Watched apps list manage karta
#    - Unread count + startup summary
#    - Programmatic toast sender (for Jarvis's own notifs)
#    - Mark-as-read management
#
#  Usage:
#    from Backend.Notifications.NotificationManager import notif_mgr
#    notif_mgr.log("WhatsApp", "Hey bhai free ho?", "Rahul")
#    notif_mgr.get_summary()         -> "Sir, you have 3 WhatsApp..."
#    notif_mgr.send("Jarvis", "Task done")  # Windows toast
# =============================================================

import json
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths

log = get_logger("NotifMgr")

# -- Optional libs --------------------------------------------
try:
    from win11toast import toast as _win11_toast
    WIN11TOAST_OK = True
except ImportError:
    WIN11TOAST_OK = False

try:
    from plyer import notification as _plyer_notif
    PLYER_OK = True
except ImportError:
    PLYER_OK = False

# =============================================================
#  Paths
# =============================================================
NOTIF_LOG_PATH = paths.DATA_DIR / "notifications.json"
WATCHED_APPS_PATH = paths.DATA_DIR / "watched_apps.json"

MAX_LOG_SIZE = 200  # keep last N notifications

DEFAULT_WATCHED = [
    "WhatsApp", "Gmail", "Outlook", "Telegram", "Discord",
    "Instagram", "Twitter", "Teams", "Slack", "Zoom",
]

# =============================================================
#  Watched apps management
# =============================================================
def _load_watched() -> List[str]:
    try:
        if WATCHED_APPS_PATH.exists():
            with open(WATCHED_APPS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Watched load: {e}")
    
    # First time - create with defaults
    _save_watched(DEFAULT_WATCHED)
    return list(DEFAULT_WATCHED)

def _save_watched(apps: List[str]):
    try:
        with open(WATCHED_APPS_PATH, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2)
    except Exception as e:
        log.error(f"Watched save: {e}")

# =============================================================
#  Log management
# =============================================================
def _load_log() -> List[Dict]:
    try:
        if NOTIF_LOG_PATH.exists():
            with open(NOTIF_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception as e:
        log.error(f"Log load: {e}")
    return []

def _save_log(log_data: List[Dict]):
    try:
        tmp = NOTIF_LOG_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(log_data[-MAX_LOG_SIZE:], f, indent=2, ensure_ascii=False)
        try:
            tmp.replace(NOTIF_LOG_PATH)
        except PermissionError:
            # OneDrive / antivirus lock fallback — write directly without atomic rename
            with open(NOTIF_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(log_data[-MAX_LOG_SIZE:], f, indent=2, ensure_ascii=False)
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as e:
        log.error(f"Log save: {e}")

# =============================================================
#  NotificationManager class
# =============================================================
class NotificationManager:
    """Central notification log + watched apps + toast sender."""
    
    # =========================================================
    #  Watched apps
    # =========================================================
    def get_watched_apps(self) -> List[str]:
        return _load_watched()
    
    def add_watched_app(self, app_name: str) -> str:
        app_name = app_name.strip().title()
        apps = _load_watched()
        if app_name not in apps:
            apps.append(app_name)
            _save_watched(apps)
            return f"Done, Sir. Now watching {app_name} notifications."
        return f"Already watching {app_name}, Sir."
    
    def remove_watched_app(self, app_name: str) -> str:
        app_name = app_name.strip().title()
        apps = _load_watched()
        if app_name in apps:
            apps.remove(app_name)
            _save_watched(apps)
            return f"Stopped watching {app_name}, Sir."
        return f"{app_name} wasn't in the watched list, Sir."
    
    def is_watched(self, app_name: str) -> bool:
        watched_lower = [a.lower() for a in _load_watched()]
        return app_name.lower() in watched_lower
    
    # =========================================================
    #  LOG NOTIFICATION
    # =========================================================
    def log(self, app: str, message: str, title: str = "", sender: str = "") -> None:
        """Record a notification."""
        entry = {
            "app": app,
            "title": title,
            "sender": sender,
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "read": False,
        }
        log_data = _load_log()
        log_data.append(entry)
        _save_log(log_data)
        log.info(f"Notification logged: [{app}] {message[:40]}")
    
    def get_unread(self) -> List[Dict]:
        return [n for n in _load_log() if not n.get("read", False)]
    
    def get_unread_count(self) -> int:
        return len(self.get_unread())
    
    def mark_all_read(self):
        data = _load_log()
        for n in data:
            n["read"] = True
        _save_log(data)
    
    def mark_app_read(self, app: str):
        """Mark notifications from specific app as read."""
        data = _load_log()
        for n in data:
            if n.get("app", "").lower() == app.lower():
                n["read"] = True
        _save_log(data)
    
    def clear_all(self):
        _save_log([])
    
    # =========================================================
    #  GET SUMMARY (for startup greeting)
    # =========================================================
    def get_summary(self) -> str:
        """Spoken summary of unread. Empty string if none."""
        unread = self.get_unread()
        if not unread:
            return ""
        
        # Group by app
        by_app: Dict[str, int] = {}
        for n in unread:
            app = n.get("app", "Unknown")
            by_app[app] = by_app.get(app, 0) + 1
        
        if not by_app:
            return ""
        
        parts = []
        for app, count in by_app.items():
            word = "message" if count == 1 else "messages"
            parts.append(f"{count} {app} {word}")
        
        if len(parts) == 1:
            return f"You have {parts[0]}, Sir."
        elif len(parts) == 2:
            return f"You have {parts[0]} and {parts[1]}, Sir."
        else:
            # "3 WhatsApp, 2 Gmail, and 1 Instagram"
            return f"You have {', '.join(parts[:-1])}, and {parts[-1]}, Sir."
    
    def get_summary_detailed(self) -> str:
        """Include sender names if available (for detailed view)."""
        unread = self.get_unread()
        if not unread:
            return ""
        
        by_app_senders: Dict[str, List[str]] = {}
        for n in unread:
            app = n.get("app", "Unknown")
            sender = n.get("sender") or n.get("title") or ""
            if sender:
                by_app_senders.setdefault(app, []).append(sender)
        
        parts = []
        for app, senders in by_app_senders.items():
            unique_senders = list(set(senders))
            if unique_senders:
                parts.append(f"{app} from {', '.join(unique_senders[:3])}")
        
        if not parts:
            return self.get_summary()
        return "Notifications, Sir: " + "; ".join(parts) + "."
    
    # =========================================================
    #  SEND TOAST (Jarvis -> Windows)
    # =========================================================
    def send(self, title: str, message: str, app_name: str = "Jarvis") -> bool:
        """Send Windows desktop notification from Jarvis."""
        # Method 1: win11toast (best for Win11)
        if WIN11TOAST_OK:
            try:
                _win11_toast(title, message, app_id=app_name)
                return True
            except Exception as e:
                log.debug(f"win11toast fail: {e}")
        
        # Method 2: plyer
        if PLYER_OK:
            try:
                _plyer_notif.notify(
                    title=title,
                    message=message,
                    app_name=app_name,
                    timeout=8,
                )
                return True
            except Exception as e:
                log.debug(f"plyer fail: {e}")
        
        # Method 3: PowerShell BurntToast (if installed)
        try:
            ps = (
                f"if (Get-Module -ListAvailable -Name BurntToast) {{"
                f"  New-BurntToastNotification -Text '{title}', '{message}'"
                f"}}"
            )
            r = subprocess.run(
                ["powershell", "-Command", ps],
                capture_output=True, timeout=6,
            )
            if r.returncode == 0 and not r.stderr:
                return True
        except Exception:
            pass
        
        log.warn(f"Couldn't send toast: {title}")
        return False

# =============================================================
#  Singleton
# =============================================================
notif_mgr = NotificationManager()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- NotificationManager Test ---\n")
    
    print("-- Watched apps --")
    watched = notif_mgr.get_watched_apps()
    print(f"  Count: {len(watched)}")
    for a in watched[:5]:
        print(f"  - {a}")
    
    print("\n-- Add test notifications --")
    notif_mgr.log("WhatsApp", "Hey bhai, free ho?", sender="Rahul")
    notif_mgr.log("WhatsApp", "Meeting at 5", sender="Work Group")
    notif_mgr.log("Gmail", "Your order has shipped", sender="Amazon", title="Order Update")
    
    print(f"  Unread count: {notif_mgr.get_unread_count()}")
    
    print(f"\n-- Summary --")
    print(f"  Short   : {notif_mgr.get_summary()}")
    print(f"  Detailed: {notif_mgr.get_summary_detailed()}")
    
    print(f"\n-- Sending test toast --")
    ok = notif_mgr.send("Jarvis Test", "Notification system working!")
    print(f"  Toast sent: {ok}")
    
    print(f"\n-- Mark all read --")
    notif_mgr.mark_all_read()
    print(f"  Unread after: {notif_mgr.get_unread_count()}")
    
    # Clean up test data
    notif_mgr.clear_all()
    
    print("\n[OK] NotificationManager test complete\n")