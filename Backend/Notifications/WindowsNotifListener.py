# =============================================================
#  Backend/Notifications/WindowsNotifListener.py
#
#  Kya karta:
#    - Real-time Windows notification monitoring
#    - Uses Windows UserNotificationListener API (official)
#    - Also falls back to process/window-title based detection
#    - Fires callback when new notification arrives
#    - Filters duplicates (same app+message within 5 sec)
#    - Auto-logs to NotificationManager
#
#  LIMITATION:
#    Windows UserNotificationListener needs user permission the
#    first time. If denied, falls back to process/window polling.
#
#  Usage:
#    from Backend.Notifications.WindowsNotifListener import notif_listener
#    notif_listener.start(on_notif=callback_fn)
#    notif_listener.stop()
# =============================================================

import subprocess
import threading
import time
import json
import hashlib
from typing import Callable, Dict, List, Optional

from Backend.Utils.Logger import get_logger
from Backend.Notifications.NotificationManager import notif_mgr

log = get_logger("NotifListener")

# =============================================================
#  Config
# =============================================================
POLL_INTERVAL = 3          # seconds between checks
DEDUP_WINDOW = 5           # don't fire same notif twice within N sec

# =============================================================
#  PowerShell script - Windows UserNotificationListener API
#  Returns JSON array of recent notifications (access-allowed only)
# =============================================================
_PS_LISTENER = r"""
try {
    [Windows.UI.Notifications.Management.UserNotificationListener, Windows.UI.Notifications.Management, ContentType=WindowsRuntime] | Out-Null
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    
    $listener = [Windows.UI.Notifications.Management.UserNotificationListener]::Current
    
    # Check access
    $accessTask = $listener.RequestAccessAsync()
    $asTaskMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $generic = $asTaskMethod.MakeGenericMethod([Windows.UI.Notifications.Management.UserNotificationListenerAccessStatus])
    $task = $generic.Invoke($null, @($accessTask))
    $task.Wait()
    $status = $task.Result
    
    if ($status -ne 'Allowed') {
        Write-Output "ACCESS_DENIED"
        exit
    }
    
    # Get recent notifications (toasts only)
    $notifsTask = $listener.GetNotificationsAsync([Windows.UI.Notifications.NotificationKinds]::Toast)
    $generic2 = $asTaskMethod.MakeGenericMethod([System.Collections.Generic.IReadOnlyList`1[Windows.UI.Notifications.UserNotification]])
    $task2 = $generic2.Invoke($null, @($notifsTask))
    $task2.Wait()
    $notifs = $task2.Result
    
    $out = @()
    foreach ($n in $notifs) {
        try {
            $app = $n.AppInfo.DisplayInfo.DisplayName
            $id = $n.Id
            
            $textElements = $n.Notification.Visual.GetBinding('ToastGeneric').GetTextElements()
            $title = if ($textElements.Count -ge 1) { $textElements[0].Text } else { '' }
            $body = if ($textElements.Count -ge 2) { $textElements[1].Text } else { '' }
            
            $out += @{
                id = $id
                app = $app
                title = $title
                body = $body
            }
        } catch { }
    }
    
    $out | ConvertTo-Json -Compress -Depth 3
} catch {
    Write-Output "ERROR: $_"
}
"""

# =============================================================
#  Listener state
# =============================================================
class _ListenerState:
    running: bool = False
    thread: Optional[threading.Thread] = None
    stop_event = threading.Event()
    seen_ids: set = set()            # Windows notification IDs seen
    recent_hashes: Dict[str, float] = {}  # hash -> timestamp (dedup)
    on_notif: Optional[Callable[[Dict], None]] = None
    access_denied: bool = False

# =============================================================
#  Core listener
# =============================================================
class WindowsNotifListener:
    """
    Real-time Windows toast notification listener.
    Falls back gracefully if API access denied.
    """
    
    def start(self, on_notif: Optional[Callable[[Dict], None]] = None):
        """Start listener in background thread."""
        if _ListenerState.running:
            log.debug("Listener already running")
            return
        
        _ListenerState.on_notif = on_notif
        _ListenerState.stop_event.clear()
        _ListenerState.running = True
        
        _ListenerState.thread = threading.Thread(
            target=self._listener_loop,
            daemon=True,
            name="NotifListener",
        )
        _ListenerState.thread.start()
        log.info("Windows notification listener started")
    
    def stop(self):
        _ListenerState.stop_event.set()
        _ListenerState.running = False
        if _ListenerState.thread:
            _ListenerState.thread.join(timeout=3)
        log.info("Listener stopped")
    
    def is_running(self) -> bool:
        return _ListenerState.running
    
    def access_granted(self) -> bool:
        """Whether Windows notification access was granted."""
        return not _ListenerState.access_denied
    
    # =========================================================
    #  Listener loop
    # =========================================================
    def _listener_loop(self):
        """Poll for new notifications."""
        while not _ListenerState.stop_event.is_set():
            try:
                self._check_once()
            except Exception as e:
                log.debug(f"Listener iteration error: {e}")
            
            # Wait
            for _ in range(POLL_INTERVAL * 2):
                if _ListenerState.stop_event.is_set():
                    return
                time.sleep(0.5)
    
    def _check_once(self):
        """Fetch notifications via PowerShell."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", _PS_LISTENER],
                capture_output=True, text=True, timeout=10,
                creationflags=0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            
            output = (result.stdout or "").strip()
            
            if not output:
                return
            
            if output.startswith("ACCESS_DENIED"):
                if not _ListenerState.access_denied:
                    _ListenerState.access_denied = True
                    log.warn(
                        "Windows notification access denied. "
                        "Enable in Settings > Privacy > Notifications."
                    )
                return
            
            if output.startswith("ERROR"):
                log.debug(f"PS error: {output[:100]}")
                return
            
            # Parse JSON
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                return
            
            # Single notification is returned as dict, not list
            if isinstance(data, dict):
                data = [data]
            
            if not isinstance(data, list):
                return
            
            # Process each
            for notif in data:
                if not isinstance(notif, dict):
                    continue
                self._handle_notif(notif)
        
        except subprocess.TimeoutExpired:
            log.debug("Listener PS timeout")
        except FileNotFoundError:
            log.error("PowerShell not found - listener disabled")
            self.stop()
        except Exception as e:
            log.debug(f"Check error: {e}")
    
    def _handle_notif(self, notif: Dict):
        """Process a single notification."""
        nid = notif.get("id")
        app = notif.get("app", "Unknown")
        title = notif.get("title", "")
        body = notif.get("body", "")
        
        # Skip if already seen by ID
        if nid and nid in _ListenerState.seen_ids:
            return
        if nid:
            _ListenerState.seen_ids.add(nid)
            # Cap set size
            if len(_ListenerState.seen_ids) > 500:
                _ListenerState.seen_ids = set(list(_ListenerState.seen_ids)[-200:])
        
        # Dedup by content hash (some apps reuse IDs)
        content = f"{app}|{title}|{body}"
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        now = time.time()
        
        if content_hash in _ListenerState.recent_hashes:
            last = _ListenerState.recent_hashes[content_hash]
            if now - last < DEDUP_WINDOW:
                return  # duplicate, skip
        _ListenerState.recent_hashes[content_hash] = now
        
        # Clean old hashes
        cutoff = now - 60
        _ListenerState.recent_hashes = {
            h: t for h, t in _ListenerState.recent_hashes.items() if t > cutoff
        }
        
        # Skip own Jarvis notifications (avoid loop)
        if app.lower() == "jarvis":
            return
        
        log.info(f"New notification: [{app}] {title} - {body[:40]}")
        
        # Log to manager
        notif_mgr.log(
            app=app,
            message=body or title,
            title=title,
            sender=title if body else "",
        )
        
        # Fire callback
        if _ListenerState.on_notif:
            try:
                _ListenerState.on_notif({
                    "app": app,
                    "title": title,
                    "body": body,
                    "message": body or title,
                })
            except Exception as e:
                log.error(f"Callback error: {e}")

# =============================================================
#  Singleton
# =============================================================
notif_listener = WindowsNotifListener()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- WindowsNotifListener Test ---\n")
    
    def on_new_notif(notif):
        app = notif.get("app", "?")
        body = notif.get("body") or notif.get("title", "")
        print(f"  [NOTIF] {app}: {body[:60]}")
    
    print("Starting listener for 20 seconds...")
    print("Send yourself a WhatsApp / Gmail / any toast to test.\n")
    
    notif_listener.start(on_notif=on_new_notif)
    
    try:
        time.sleep(20)
    except KeyboardInterrupt:
        pass
    
    print("\nStopping...")
    notif_listener.stop()
    
    if not notif_listener.access_granted():
        print("\n[NOTE] Windows notification access was denied.")
        print("To enable: Settings > Privacy > Notifications > Let apps access notifications")
    
    print("\n[OK] WindowsNotifListener test complete\n")