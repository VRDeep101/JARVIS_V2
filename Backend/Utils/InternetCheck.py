# ═════════════════════════════════════════════════════════════
#  Backend/Utils/InternetCheck.py  —  Network Status
#
#  Kya karta:
#    - Internet availability check karta (fast, cached)
#    - Background thread me continuous monitoring
#    - State change pe callbacks fire karta
#    - Specific API reachability test karta (Groq, Cohere, etc.)
#
#  Usage:
#    from Backend.Utils.InternetCheck import net
#    net.is_online()           → True/False
#    net.wait_for_online(30)   → blocks until online (or timeout)
#    net.on_state_change(fn)   → callback(is_online: bool)
#    net.api_reachable("groq") → True/False
# ═════════════════════════════════════════════════════════════

import socket
import threading
import time
from typing import Callable, List, Optional

from Backend.Utils.Logger import get_logger

log = get_logger("InternetCheck")

# ── Test endpoints (fast, reliable) ───────────────────────────
_DNS_HOSTS = [
    ("8.8.8.8", 53),        # Google DNS
    ("1.1.1.1", 53),        # Cloudflare DNS
    ("208.67.222.222", 53), # OpenDNS
]

_API_ENDPOINTS = {
    "groq":         "api.groq.com",
    "cohere":       "api.cohere.com",
    "huggingface":  "huggingface.co",
    "gemini":       "generativelanguage.googleapis.com",
    "openweather":  "api.openweathermap.org",
    "newsapi":      "newsapi.org",
    "wolfram":      "api.wolframalpha.com",
    "duckduckgo":   "duckduckgo.com",
    "wikipedia":    "en.wikipedia.org",
    "google":       "www.google.com",
}

# ── Config ────────────────────────────────────────────────────
_CHECK_INTERVAL = 5        # seconds between checks
_TIMEOUT_SEC    = 2        # socket timeout
_CACHE_TTL      = 3        # cache result for N seconds

# ── State ─────────────────────────────────────────────────────
class _NetState:
    online: bool = False
    last_check: float = 0.0
    monitor_thread: Optional[threading.Thread] = None
    callbacks: List[Callable[[bool], None]] = []
    _lock = threading.Lock()

# ── Core checks ───────────────────────────────────────────────
def _socket_check(host: str, port: int, timeout: float = _TIMEOUT_SEC) -> bool:
    """Try opening a TCP socket to host:port. Returns True on success."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def _check_internet() -> bool:
    """Ping DNS servers — fast, doesn't need HTTP."""
    for host, port in _DNS_HOSTS:
        if _socket_check(host, port):
            return True
    return False

# ── Public API ────────────────────────────────────────────────
class Net:
    """Network status checker."""
    
    def is_online(self, force: bool = False) -> bool:
        """
        Returns current online status.
        Cached for _CACHE_TTL seconds unless force=True.
        """
        now = time.time()
        if not force and (now - _NetState.last_check) < _CACHE_TTL:
            return _NetState.online
        
        online = _check_internet()
        _NetState.last_check = now
        
        # Fire callbacks if state changed
        if online != _NetState.online:
            old = _NetState.online
            _NetState.online = online
            log.info(f"Net status: {'ONLINE' if online else 'OFFLINE'}")
            for cb in list(_NetState.callbacks):
                try:
                    cb(online)
                except Exception as e:
                    log.error(f"Callback error: {e}")
        
        _NetState.online = online
        return online
    
    def wait_for_online(self, timeout: float = 30.0) -> bool:
        """Block until online, or timeout. Returns final status."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.is_online(force=True):
                return True
            time.sleep(1)
        return False
    
    def on_state_change(self, callback: Callable[[bool], None]):
        """Register a callback fired when net state changes."""
        with _NetState._lock:
            if callback not in _NetState.callbacks:
                _NetState.callbacks.append(callback)
    
    def api_reachable(self, api_key: str) -> bool:
        """Check if a specific API endpoint is reachable."""
        host = _API_ENDPOINTS.get(api_key.lower())
        if not host:
            return False
        return _socket_check(host, 443, timeout=3)
    
    def check_all_apis(self) -> dict:
        """Check every configured API. Returns {name: bool}."""
        result = {}
        for name, host in _API_ENDPOINTS.items():
            result[name] = _socket_check(host, 443, timeout=2)
        return result
    
    def start_monitor(self, interval: int = _CHECK_INTERVAL):
        """Start background thread that checks every N seconds."""
        if _NetState.monitor_thread and _NetState.monitor_thread.is_alive():
            return
        
        def _monitor():
            while True:
                try:
                    self.is_online(force=True)
                    time.sleep(interval)
                except Exception as e:
                    log.error(f"Monitor error: {e}")
                    time.sleep(interval)
        
        _NetState.monitor_thread = threading.Thread(
            target=_monitor, daemon=True, name="NetMonitor"
        )
        _NetState.monitor_thread.start()
        log.info(f"Net monitor started (interval={interval}s)")

# ── Singleton ─────────────────────────────────────────────────
net = Net()

# =============================================================
#  Main.py compat: register callback on net state change
# =============================================================
import threading as _threading
import time as _time

_net_callbacks = []
_net_last_state = None
_net_monitor_thread = None
_net_monitor_running = False

def _net_monitor_loop():
    """Background thread watching net state, fires callbacks on change."""
    global _net_last_state, _net_monitor_running
    while _net_monitor_running:
        try:
            current = net.is_online()
            if _net_last_state is not None and current != _net_last_state:
                # State changed - fire callbacks
                for cb in list(_net_callbacks):
                    try:
                        cb(current)
                    except Exception:
                        pass
            _net_last_state = current
        except Exception:
            pass
        _time.sleep(5)  # check every 5 sec

def _register_callback(callback):
    """Register callback(online: bool) called on net state change."""
    global _net_monitor_thread, _net_monitor_running
    _net_callbacks.append(callback)
    
    # Start monitor thread on first registration
    if _net_monitor_thread is None:
        _net_monitor_running = True
        _net_monitor_thread = _threading.Thread(
            target=_net_monitor_loop, daemon=True, name="NetMonitor"
        )
        _net_monitor_thread.start()

# Attach to net singleton
net.register_callback = _register_callback

# ── Test block ────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n─── InternetCheck Test ───\n")
    
    print(f"Online right now: {net.is_online(force=True)}")
    
    print("\n── API Reachability ──")
    results = net.check_all_apis()
    for name, reachable in results.items():
        icon = "✓" if reachable else "✗"
        print(f"  {icon} {name:15} ({_API_ENDPOINTS[name]})")
    
    print("\n── State Change Callback ──")
    def on_change(online):
        print(f"  CALLBACK: Net is now {'ONLINE' if online else 'OFFLINE'}")
    
    net.on_state_change(on_change)
    
    print("\n── Starting monitor for 10 seconds ──")
    net.start_monitor(interval=3)
    time.sleep(10)
    
    print("\n✓ InternetCheck test complete\n")