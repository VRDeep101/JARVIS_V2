# =============================================================
#  Backend/Automation/SystemControl.py - Windows System Controls
#
#  Kya karta:
#    - Volume up/down/mute (pycaw)
#    - Brightness up/down (screen-brightness-control)
#    - Screenshot (pyautogui + Pictures folder)
#    - Screen recording (Game Bar Win+Alt+R)
#    - Lock screen (with confirmation callback)
#    - Bluetooth on/off (PowerShell)
#    - WiFi info (netsh)
#    - Battery status
#    - System stats (for GUI: CPU/RAM/disk/net)
#
#  Usage:
#    from Backend.Automation.SystemControl import system
#    system.volume_up()
#    system.screenshot()
#    system.lock_screen(confirmed=True)
#    stats = system.get_stats()
# =============================================================

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths

log = get_logger("SystemControl")

# -- Optional deps --------------------------------------------
try:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    PYCAW_OK = True
except Exception:
    PYCAW_OK = False
    log.warn("pycaw not available - volume control disabled")

try:
    import screen_brightness_control as sbc
    SBC_OK = True
except Exception:
    SBC_OK = False
    log.warn("screen-brightness-control unavailable")

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

# =============================================================
#  CONFIG
# =============================================================
VOLUME_STEP     = 0.10   # 10%
BRIGHTNESS_STEP = 10     # 10%

SCREENSHOT_DIR = paths.SCREENSHOTS_DIR
RECORDING_DIR  = paths.RECORDINGS_DIR

# =============================================================
#  VOLUME
# =============================================================
def _get_master_volume():
    """Internal: get Windows master volume interface."""
    if not PYCAW_OK:
        return None
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        from ctypes import cast, POINTER
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return volume
    except Exception as e:
        log.error(f"Get volume interface error: {e}")
        return None

class SystemControl:
    """Main system controls."""
    
    # =========================================================
    #  VOLUME
    # =========================================================
    def volume_up(self, step: float = VOLUME_STEP) -> Dict:
        """Increase volume by step (default 10%)."""
        vol = _get_master_volume()
        if not vol:
            return {"ok": False, "message": "Audio control unavailable, Sir."}
        try:
            current = vol.GetMasterVolumeLevelScalar()
            new = min(1.0, current + step)
            vol.SetMasterVolumeLevelScalar(new, None)
            log.action(f"Volume: {int(current*100)}% -> {int(new*100)}%")
            return {"ok": True, "message": f"Volume at {int(new*100)}%, Sir.",
                    "old": int(current*100), "new": int(new*100)}
        except Exception as e:
            log.error(f"Volume up error: {e}")
            return {"ok": False, "message": str(e)}
    
    def volume_down(self, step: float = VOLUME_STEP) -> Dict:
        """Decrease volume by step."""
        vol = _get_master_volume()
        if not vol:
            return {"ok": False, "message": "Audio control unavailable, Sir."}
        try:
            current = vol.GetMasterVolumeLevelScalar()
            new = max(0.0, current - step)
            vol.SetMasterVolumeLevelScalar(new, None)
            log.action(f"Volume: {int(current*100)}% -> {int(new*100)}%")
            return {"ok": True, "message": f"Volume at {int(new*100)}%, Sir.",
                    "old": int(current*100), "new": int(new*100)}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def volume_set(self, percent: int) -> Dict:
        """Set absolute volume (0-100)."""
        vol = _get_master_volume()
        if not vol:
            return {"ok": False, "message": "Audio control unavailable, Sir."}
        try:
            level = max(0, min(100, percent)) / 100.0
            vol.SetMasterVolumeLevelScalar(level, None)
            log.action(f"Volume set to {percent}%")
            return {"ok": True, "message": f"Volume at {percent}%, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def mute(self) -> Dict:
        """Toggle mute."""
        vol = _get_master_volume()
        if not vol:
            return {"ok": False, "message": "Audio control unavailable, Sir."}
        try:
            vol.SetMute(1, None)
            log.action("Muted")
            return {"ok": True, "message": "Audio muted, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def unmute(self) -> Dict:
        """Unmute."""
        vol = _get_master_volume()
        if not vol:
            return {"ok": False, "message": "Audio control unavailable, Sir."}
        try:
            vol.SetMute(0, None)
            log.action("Unmuted")
            return {"ok": True, "message": "Audio is back on, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def get_volume(self) -> Optional[int]:
        """Current volume 0-100, or None."""
        vol = _get_master_volume()
        if not vol:
            return None
        try:
            return int(vol.GetMasterVolumeLevelScalar() * 100)
        except Exception:
            return None
    
    # =========================================================
    #  BRIGHTNESS
    # =========================================================
    def brightness_up(self, step: int = BRIGHTNESS_STEP) -> Dict:
        if not SBC_OK:
            return {"ok": False, "message": "Brightness control unavailable, Sir."}
        try:
            current = sbc.get_brightness(display=0)
            if isinstance(current, list):
                current = current[0] if current else 50
            new = min(100, current + step)
            sbc.set_brightness(new, display=0)
            log.action(f"Brightness: {current}% -> {new}%")
            return {"ok": True, "message": f"Brightness at {new}%, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def brightness_down(self, step: int = BRIGHTNESS_STEP) -> Dict:
        if not SBC_OK:
            return {"ok": False, "message": "Brightness control unavailable, Sir."}
        try:
            current = sbc.get_brightness(display=0)
            if isinstance(current, list):
                current = current[0] if current else 50
            new = max(0, current - step)
            sbc.set_brightness(new, display=0)
            log.action(f"Brightness: {current}% -> {new}%")
            return {"ok": True, "message": f"Brightness at {new}%, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def brightness_set(self, percent: int) -> Dict:
        if not SBC_OK:
            return {"ok": False, "message": "Brightness control unavailable, Sir."}
        try:
            level = max(0, min(100, percent))
            sbc.set_brightness(level, display=0)
            log.action(f"Brightness set to {level}%")
            return {"ok": True, "message": f"Brightness at {level}%, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def get_brightness(self) -> Optional[int]:
        if not SBC_OK:
            return None
        try:
            val = sbc.get_brightness(display=0)
            return val[0] if isinstance(val, list) and val else val
        except Exception:
            return None
    
    # =========================================================
    #  SCREENSHOT
    # =========================================================
    def screenshot(self) -> Dict:
        """Take screenshot, save to Data/Screenshots/, open it."""
        if not PYAUTOGUI_OK:
            return {"ok": False, "message": "Screenshot unavailable, Sir."}
        try:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = SCREENSHOT_DIR / filename
            
            img = pyautogui.screenshot()
            img.save(str(filepath))
            
            log.action(f"Screenshot: {filepath.name}")
            
            # Auto-open
            try:
                os.startfile(str(filepath))
            except Exception:
                pass
            
            return {
                "ok": True,
                "message": "Screenshot captured, Sir.",
                "path": str(filepath),
            }
        except Exception as e:
            log.error(f"Screenshot error: {e}")
            return {"ok": False, "message": str(e)}
    
    # =========================================================
    #  SCREEN RECORDING (Windows Game Bar)
    # =========================================================
    def start_recording(self) -> Dict:
        """Start screen recording via Win+Alt+R."""
        if not KEYBOARD_OK:
            return {"ok": False, "message": "Recording unavailable, Sir."}
        try:
            _kb.press_and_release("windows+alt+r")
            log.action("Started screen recording")
            return {
                "ok": True,
                "message": "Screen recording started, Sir. Say 'stop recording' when done.",
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def stop_recording(self) -> Dict:
        """Stop screen recording (same hotkey)."""
        if not KEYBOARD_OK:
            return {"ok": False, "message": "Recording unavailable, Sir."}
        try:
            _kb.press_and_release("windows+alt+r")
            log.action("Stopped screen recording")
            return {
                "ok": True,
                "message": "Recording saved, Sir. Check Videos/Captures folder.",
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    # =========================================================
    #  LOCK SCREEN
    # =========================================================
    def lock_screen(self, confirmed: bool = False) -> Dict:
        """
        Lock Windows. Requires confirmed=True.
        Caller should prompt user and pass confirmation.
        """
        if not confirmed:
            return {
                "ok": False,
                "needs_confirmation": True,
                "message": "Lock the screen, Sir? Say 'yes lock' to confirm.",
            }
        
        try:
            if KEYBOARD_OK:
                _kb.press_and_release("windows+l")
            else:
                os.system("rundll32.exe user32.dll,LockWorkStation")
            log.action("Screen locked")
            return {"ok": True, "message": "Locking now, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    # =========================================================
    #  BLUETOOTH
    # =========================================================
    def bluetooth_on(self) -> Dict:
        """Turn on Bluetooth via PowerShell."""
        ps = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? "
            "{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
            "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0];"
            "Function Await($WinRtTask, $ResultType) {"
            "$asTask = $asTaskGeneric.MakeGenericMethod($ResultType);"
            "$netTask = $asTask.Invoke($null, @($WinRtTask));"
            "$netTask.Wait(-1) | Out-Null;"
            "$netTask.Result };"
            "[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null;"
            "$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) "
            "([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]);"
            "$bluetooth = $radios | ? { $_.Kind -eq 'Bluetooth' };"
            "[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null;"
            "Await ($bluetooth.SetStateAsync('On')) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null"
        )
        try:
            subprocess.run(
                ["powershell", "-Command", ps],
                capture_output=True, timeout=10,
            )
            log.action("Bluetooth ON")
            return {"ok": True, "message": "Bluetooth enabled, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def bluetooth_off(self) -> Dict:
        """Turn off Bluetooth."""
        ps = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? "
            "{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
            "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0];"
            "Function Await($WinRtTask, $ResultType) {"
            "$asTask = $asTaskGeneric.MakeGenericMethod($ResultType);"
            "$netTask = $asTask.Invoke($null, @($WinRtTask));"
            "$netTask.Wait(-1) | Out-Null;"
            "$netTask.Result };"
            "[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null;"
            "$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) "
            "([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]);"
            "$bluetooth = $radios | ? { $_.Kind -eq 'Bluetooth' };"
            "[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null;"
            "Await ($bluetooth.SetStateAsync('Off')) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null"
        )
        try:
            subprocess.run(
                ["powershell", "-Command", ps],
                capture_output=True, timeout=10,
            )
            log.action("Bluetooth OFF")
            return {"ok": True, "message": "Bluetooth disabled, Sir."}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    # =========================================================
    #  BATTERY
    # =========================================================
    def battery_status(self) -> Optional[Dict]:
        """Get battery info."""
        if not PSUTIL_OK:
            return None
        try:
            bat = psutil.sensors_battery()
            if bat is None:
                return None
            return {
                "percent": int(bat.percent),
                "plugged": bat.power_plugged,
                "time_left_minutes": bat.secsleft // 60 if bat.secsleft > 0 else None,
            }
        except Exception:
            return None
    
    # =========================================================
    #  SYSTEM STATS (for GUI)
    # =========================================================
    def get_stats(self) -> Dict:
        """Full system stats dict."""
        stats = {
            "cpu_percent": None,
            "ram_percent": None,
            "ram_used_gb": None,
            "ram_total_gb": None,
            "disk_percent": None,
            "net_up_kbps": None,
            "net_down_kbps": None,
            "battery": None,
            "volume": self.get_volume(),
            "brightness": self.get_brightness(),
        }
        
        if PSUTIL_OK:
            try:
                stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
                ram = psutil.virtual_memory()
                stats["ram_percent"] = ram.percent
                stats["ram_used_gb"] = round(ram.used / (1024**3), 1)
                stats["ram_total_gb"] = round(ram.total / (1024**3), 1)
                disk = psutil.disk_usage("C:\\")
                stats["disk_percent"] = disk.percent
                stats["battery"] = self.battery_status()
            except Exception as e:
                log.debug(f"Stats error: {e}")
        
        return stats

# =============================================================
#  Singleton
# =============================================================
system = SystemControl()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- SystemControl Test ---\n")
    
    # Read-only tests (safe)
    print(f"Current volume    : {system.get_volume()}%")
    print(f"Current brightness: {system.get_brightness()}%")
    
    bat = system.battery_status()
    if bat:
        print(f"Battery           : {bat['percent']}% | plugged: {bat['plugged']}")
    
    print("\n-- System Stats --")
    stats = system.get_stats()
    for k, v in stats.items():
        print(f"  {k:20} : {v}")
    
    # Interactive test prompt
    print("\n-- Live tests (optional, comment out if you want to skip) --\n")
    print("Uncomment below to test vol/brightness/screenshot live")
    
    # Uncomment to test live:
    # print("Volume up...")
    # print(system.volume_up())
    # time.sleep(1)
    # print("Volume down...")
    # print(system.volume_down())
    # time.sleep(1)
    # 
    # print("Brightness up...")
    # print(system.brightness_up())
    # time.sleep(1)
    # print("Brightness down...")
    # print(system.brightness_down())
    # time.sleep(1)
    #
    # print("Screenshot...")
    # r = system.screenshot()
    # print(f"  Path: {r.get('path')}")
    
    print("\n[OK] SystemControl test complete\n")