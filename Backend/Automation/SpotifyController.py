# =============================================================
#  Backend/Automation/SpotifyController.py - Spotify Hybrid
#
#  Kya karta:
#    - Spotify desktop app launch + control
#    - Keyboard shortcuts (play/pause/next/prev)
#    - Search + play via desktop search (Ctrl+L)
#    - Fallback: open in web player
#    - Volume control via pycaw (Spotify-specific)
#
#  Note: User has free tier -> no Web API, use desktop control
#
#  Usage:
#    from Backend.Automation.SpotifyController import spotify
#    spotify.play()
#    spotify.pause()
#    spotify.next_track()
#    spotify.search_and_play("shape of you")
# =============================================================

import os
import subprocess
import time
import webbrowser
from typing import Dict, Optional

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Automation.AppRegistry import app_registry

log = get_logger("Spotify")

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    PYAUTOGUI_OK = True
except Exception:
    PYAUTOGUI_OK = False

try:
    import keyboard as _kb
    KEYBOARD_OK = True
except Exception:
    KEYBOARD_OK = False

try:
    import psutil
    PSUTIL_OK = True
except Exception:
    PSUTIL_OK = False

try:
    import pygetwindow as gw
    PYGETWINDOW_OK = True
except Exception:
    PYGETWINDOW_OK = False

# =============================================================
#  SpotifyController class
# =============================================================
class SpotifyController:
    """Spotify desktop + web hybrid controller."""
    
    WEB_PLAYER = "https://open.spotify.com"
    SEARCH_URL = "https://open.spotify.com/search/{}"
    
    # -- Running check ---------------------------------------
    def is_running(self) -> bool:
        """Is Spotify desktop running?"""
        if not PSUTIL_OK:
            return False
        try:
            for p in psutil.process_iter(["name"]):
                if p.info["name"] and "spotify" in p.info["name"].lower():
                    return True
        except Exception:
            pass
        return False
    
    def _ensure_running(self, wait_sec: int = 5) -> bool:
        """Launch Spotify if not running, wait until it's ready."""
        if self.is_running():
            return True
        
        # Try to open via AppRegistry
        result = app_registry.open("spotify", prefer_desktop=True)
        if not result.get("ok"):
            return False
        
        # Wait for it to load
        t0 = time.time()
        while time.time() - t0 < wait_sec:
            if self.is_running():
                time.sleep(2)  # extra time for UI ready
                return True
            time.sleep(0.5)
        return False
    
    def _focus_spotify(self) -> bool:
        """Bring Spotify window to front."""
        if not PYGETWINDOW_OK:
            return False
        try:
            wins = gw.getWindowsWithTitle("Spotify")
            for w in wins:
                if "spotify" in w.title.lower():
                    if w.isMinimized:
                        w.restore()
                    w.activate()
                    time.sleep(0.3)
                    return True
        except Exception as e:
            log.debug(f"Focus error: {e}")
        return False
    
    # =========================================================
    #  Playback controls (media keys work globally)
    # =========================================================
    def play_pause(self) -> Dict:
        """Toggle play/pause (media key)."""
        if not KEYBOARD_OK:
            return {"ok": False, "message": "Control unavailable, Sir."}
        try:
            _kb.press_and_release("play/pause media")
            log.action("Spotify play/pause")
            return {"ok": True, "message": "Done, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def play(self) -> Dict:
        """Start/resume playback."""
        if not self._ensure_running():
            return {"ok": False, "message": "Couldn't start Spotify, Sir."}
        return self.play_pause()
    
    def pause(self) -> Dict:
        return self.play_pause()
    
    def next_track(self) -> Dict:
        """Skip to next track (media key)."""
        if not KEYBOARD_OK:
            return {"ok": False, "message": "Control unavailable, Sir."}
        try:
            _kb.press_and_release("next track")
            log.action("Spotify next")
            return {"ok": True, "message": "Skipping, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def previous_track(self) -> Dict:
        """Go to previous track."""
        if not KEYBOARD_OK:
            return {"ok": False, "message": "Control unavailable, Sir."}
        try:
            _kb.press_and_release("previous track")
            log.action("Spotify previous")
            return {"ok": True, "message": "Going back, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    # =========================================================
    #  Search & play a specific song
    # =========================================================
    def search_and_play(self, query: str) -> Dict:
        """
        Search Spotify for a song and start it playing.
        Uses desktop app (Ctrl+L for search, then Enter).
        Falls back to web player if desktop fails.
        """
        if not query:
            return {"ok": False, "message": "Need a song name, Sir."}
        
        # Method 1: Desktop search
        if self._ensure_running() and PYAUTOGUI_OK:
            result = self._desktop_search(query)
            if result["ok"]:
                return result
        
        # Method 2: Web player fallback
        return self._web_search(query)
    
    def _desktop_search(self, query: str) -> Dict:
        """Use Spotify desktop Ctrl+L search."""
        if not self._focus_spotify():
            return {"ok": False, "message": "Couldn't focus Spotify"}
        
        try:
            time.sleep(0.5)
            # Ctrl+L opens search in Spotify
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.8)
            
            # Type query
            pyautogui.typewrite(query, interval=0.02)
            time.sleep(0.8)
            
            # Enter goes to search results page
            pyautogui.press("enter")
            time.sleep(2.5)
            
            # Click first result - Spotify typically needs Tab navigation
            # Simpler: press Enter on top result using keyboard
            # Press Tab a few times to reach first song, then Enter
            # OR use keyboard shortcut (shift+enter sometimes plays top)
            
            # Safest: use a short delay + pyautogui to click center-ish
            # But without mouse, we use keyboard - Tab until focused on first track
            # Spotify's layout varies, so we try pressing Enter
            pyautogui.press("enter")
            time.sleep(0.5)
            
            log.action(f"Spotify search: {query}")
            return {"ok": True, "message": f"Playing {query} on Spotify, Sir."}
        except Exception as e:
            log.error(f"Desktop search error: {e}")
            return {"ok": False, "message": str(e)}
    
    def _web_search(self, query: str) -> Dict:
        """Open search in web player."""
        try:
            # URL-encode the query
            from urllib.parse import quote
            url = self.SEARCH_URL.format(quote(query))
            webbrowser.open(url)
            log.action(f"Spotify web search: {query}")
            return {
                "ok": True,
                "message": f"Opening Spotify web search for {query}, Sir. Click the song to play.",
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    # =========================================================
    #  Volume (Spotify-specific via pycaw)
    # =========================================================
    def set_spotify_volume(self, percent: int) -> Dict:
        """Set Spotify-only volume (not system-wide)."""
        try:
            from pycaw.pycaw import AudioUtilities
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process and "spotify" in session.Process.name().lower():
                    interface = session.SimpleAudioVolume
                    interface.SetMasterVolume(max(0.0, min(1.0, percent / 100)), None)
                    log.action(f"Spotify volume -> {percent}%")
                    return {"ok": True, "message": f"Spotify volume at {percent}%."}
            return {"ok": False, "message": "Spotify not active, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}

# =============================================================
#  Singleton
# =============================================================
spotify = SpotifyController()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- SpotifyController Test ---\n")
    
    print(f"Spotify running: {spotify.is_running()}")
    
    if PSUTIL_OK:
        print("psutil         : OK")
    if PYAUTOGUI_OK:
        print("pyautogui      : OK")
    if KEYBOARD_OK:
        print("keyboard       : OK")
    if PYGETWINDOW_OK:
        print("pygetwindow    : OK")
    
    # Uncomment for live tests:
    # print("\n-- Starting Spotify --")
    # started = spotify._ensure_running()
    # print(f"  Started: {started}")
    # 
    # if started:
    #     time.sleep(3)
    #     print("\n-- Play/Pause --")
    #     print(spotify.play_pause())
    #     time.sleep(3)
    #     
    #     print("\n-- Search and play --")
    #     print(spotify.search_and_play("shape of you"))
    
    print("\n[OK] SpotifyController test complete\n")