# =============================================================
#  Backend/Modes/GamingMode.py - ASUS TUF A15 Gaming
#
#  Kya karta:
#    - Activates Windows Ultimate Performance power plan
#    - Real-time monitoring: CPU/GPU temp, RAM, battery
#    - Alerts: thermal (>85C GPU, >90C CPU), low battery, high RAM
#    - Quick commands during gaming: screenshot, volume, discord mute
#    - Game detection (auto-notice when game launches - optional)
#    - Post-gaming session summary
#
#  Hardware specific to: ASUS TUF A15, Ryzen 7 7445HS, RTX 3050
#
#  Usage:
#    from Backend.Modes.GamingMode import gaming_mode
#    gaming_mode.enter(on_speak=tts_cb)
#    gaming_mode.get_stats()  # during gaming
#    gaming_mode.exit()  # auto-generates session summary
# =============================================================

import subprocess
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

from Backend.Utils.Logger import get_logger
from Backend.Core.ModeManager import mode_manager, Mode

log = get_logger("GamingMode")

# -- Optional deps --------------------------------------------
try:
    import psutil
    PSUTIL_OK = True
except Exception:
    PSUTIL_OK = False

try:
    import GPUtil
    GPUTIL_OK = True
except Exception:
    GPUTIL_OK = False

# =============================================================
#  CONFIG - THERMAL THRESHOLDS (ASUS TUF A15 specific)
# =============================================================
CPU_TEMP_WARN = 85     # degrees C
CPU_TEMP_CRIT = 92
GPU_TEMP_WARN = 80
GPU_TEMP_CRIT = 87
BATTERY_WARN = 25      # percent
BATTERY_CRIT = 12
RAM_WARN = 85          # percent

MONITOR_INTERVAL = 15  # seconds between health checks
ALERT_COOLDOWN = 60    # seconds - don't re-alert same issue

# =============================================================
#  GamingMode class
# =============================================================
class GamingMode:
    """ASUS TUF A15 gaming performance + monitoring."""
    
    def __init__(self):
        self.active = False
        self.on_speak: Optional[Callable] = None
        
        self.session_start: Optional[datetime] = None
        self.session_stats: Dict = {}
        
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_alerts: Dict[str, float] = {}  # throttle alerts
        
        # Stats aggregation
        self._cpu_samples: List[float] = []
        self._gpu_samples: List[float] = []
        self._cpu_temp_peak = 0
        self._gpu_temp_peak = 0
        self._battery_start: Optional[int] = None
    
    # =========================================================
    #  ENTER / EXIT
    # =========================================================
    def enter(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        """Activate Gaming mode."""
        self.active = True
        self.on_speak = on_speak
        self._stop_event.clear()
        
        self.session_start = datetime.now()
        self._cpu_samples = []
        self._gpu_samples = []
        self._cpu_temp_peak = 0
        self._gpu_temp_peak = 0
        
        # Record starting battery
        if PSUTIL_OK:
            try:
                bat = psutil.sensors_battery()
                if bat:
                    self._battery_start = int(bat.percent)
            except Exception:
                pass
        
        # Activate Ultimate Performance power plan (if available)
        self._set_power_plan_ultimate()
        
        announce = mode_manager.current_info["voice_announce"]
        log.info("Gaming mode entered")
        
        if on_speak:
            on_speak(announce)
        
        # Start health monitor
        self._start_monitor()
        
        return announce
    
    def exit(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        """Deactivate - show session summary."""
        self.active = False
        self._stop_event.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
        
        # Restore balanced power plan
        self._set_power_plan_balanced()
        
        # Build session summary
        summary = self._build_session_summary()
        log.info(f"Gaming session: {summary}")
        
        msg = f"Gaming mode deactivated, Sir. {summary}"
        if on_speak:
            on_speak(msg)
        
        self.session_start = None
        return msg
    
    def is_active(self) -> bool:
        return self.active and mode_manager.current_mode == Mode.GAMING
    
    # =========================================================
    #  POWER PLAN
    # =========================================================
    def _set_power_plan_ultimate(self):
        """Enable Ultimate Performance if not already."""
        try:
            # Check if Ultimate Performance exists
            result = subprocess.run(
                ["powercfg", "-list"],
                capture_output=True, text=True, timeout=5,
            )
            if "Ultimate Performance" in result.stdout:
                # Extract GUID
                for line in result.stdout.splitlines():
                    if "Ultimate Performance" in line:
                        import re
                        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", line)
                        if m:
                            guid = m.group(1)
                            subprocess.run(["powercfg", "-setactive", guid],
                                           capture_output=True, timeout=5)
                            log.info("Ultimate Performance power plan activated")
                            return
            
            # If not available, try to add it
            subprocess.run(
                ["powercfg", "-duplicatescheme",
                 "e9a42b02-d5df-448d-aa00-03f14749eb61"],  # Ultimate Perf GUID
                capture_output=True, timeout=5,
            )
        except Exception as e:
            log.debug(f"Power plan set error: {e}")
    
    def _set_power_plan_balanced(self):
        """Restore balanced plan."""
        try:
            subprocess.run(
                ["powercfg", "-setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"],
                capture_output=True, timeout=5,
            )
            log.info("Balanced power plan restored")
        except Exception:
            pass
    
    # =========================================================
    #  HEALTH MONITOR (background thread)
    # =========================================================
    def _start_monitor(self):
        """Start health-check background thread."""
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="GamingMonitor",
        )
        self._monitor_thread.start()
        log.info("Gaming health monitor started")
    
    def _monitor_loop(self):
        """Check thermal/battery/RAM every N seconds."""
        while not self._stop_event.is_set():
            try:
                stats = self.get_stats()
                self._check_alerts(stats)
                
                # Record samples
                if stats.get("cpu_percent") is not None:
                    self._cpu_samples.append(stats["cpu_percent"])
                if stats.get("gpu_load") is not None:
                    self._gpu_samples.append(stats["gpu_load"])
                if stats.get("cpu_temp"):
                    self._cpu_temp_peak = max(self._cpu_temp_peak, stats["cpu_temp"])
                if stats.get("gpu_temp"):
                    self._gpu_temp_peak = max(self._gpu_temp_peak, stats["gpu_temp"])
            except Exception as e:
                log.debug(f"Monitor loop error: {e}")
            
            # Wait
            for _ in range(MONITOR_INTERVAL * 2):
                if self._stop_event.is_set():
                    return
                time.sleep(0.5)
    
    def _check_alerts(self, stats: Dict):
        """Evaluate stats and speak alerts if needed."""
        now = time.time()
        
        def _should_alert(key: str) -> bool:
            last = self._last_alerts.get(key, 0)
            if now - last < ALERT_COOLDOWN:
                return False
            self._last_alerts[key] = now
            return True
        
        # CPU temp
        cpu_temp = stats.get("cpu_temp")
        if cpu_temp:
            if cpu_temp >= CPU_TEMP_CRIT and _should_alert("cpu_crit"):
                self._alert(f"Sir, CPU critical at {cpu_temp:.0f} degrees. Reduce graphics or pause.")
            elif cpu_temp >= CPU_TEMP_WARN and _should_alert("cpu_warn"):
                self._alert(f"Sir, CPU temp climbing, {cpu_temp:.0f} degrees.")
        
        # GPU temp
        gpu_temp = stats.get("gpu_temp")
        if gpu_temp:
            if gpu_temp >= GPU_TEMP_CRIT and _should_alert("gpu_crit"):
                self._alert(f"Sir, GPU critical at {gpu_temp:.0f} degrees. Thermal throttling imminent.")
            elif gpu_temp >= GPU_TEMP_WARN and _should_alert("gpu_warn"):
                self._alert(f"Sir, GPU warming up, {gpu_temp:.0f} degrees.")
        
        # Battery
        battery = stats.get("battery")
        if battery:
            bat_pct = battery.get("percent", 100)
            plugged = battery.get("plugged", True)
            
            if not plugged:
                if bat_pct <= BATTERY_CRIT and _should_alert("bat_crit"):
                    self._alert(f"Sir, critical battery, {bat_pct}%. Plug in or save and close.")
                elif bat_pct <= BATTERY_WARN and _should_alert("bat_warn"):
                    self._alert(f"Sir, battery at {bat_pct}%. Consider plugging in.")
        
        # RAM
        ram_pct = stats.get("ram_percent", 0)
        if ram_pct >= RAM_WARN and _should_alert("ram"):
            self._alert(f"Sir, memory at {ram_pct}%. Close something if you can.")
    
    def _alert(self, message: str):
        log.warn(f"GAMING ALERT: {message}")
        if self.on_speak:
            try:
                self.on_speak(message)
            except Exception as e:
                log.error(f"Alert speak error: {e}")
    
    # =========================================================
    #  GET STATS
    # =========================================================
    def get_stats(self) -> Dict:
        """Current gaming-relevant stats."""
        stats = {
            "cpu_percent": None,
            "cpu_temp": None,
            "gpu_load": None,
            "gpu_temp": None,
            "gpu_mem_used_mb": None,
            "ram_percent": None,
            "battery": None,
        }
        
        if PSUTIL_OK:
            try:
                stats["cpu_percent"] = psutil.cpu_percent(interval=0.2)
                ram = psutil.virtual_memory()
                stats["ram_percent"] = ram.percent
                
                # Battery
                try:
                    bat = psutil.sensors_battery()
                    if bat:
                        stats["battery"] = {
                            "percent": int(bat.percent),
                            "plugged": bat.power_plugged,
                        }
                except Exception:
                    pass
                
                # CPU temp - psutil.sensors_temperatures on Windows usually empty
                # OpenHardwareMonitor integration would be ideal; skipped here
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for name, entries in temps.items():
                            if entries:
                                stats["cpu_temp"] = entries[0].current
                                break
                except Exception:
                    pass
            except Exception as e:
                log.debug(f"Stats psutil error: {e}")
        
        # GPU via nvidia-smi or GPUtil
        if GPUTIL_OK:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    stats["gpu_load"] = round(gpu.load * 100, 1)
                    stats["gpu_temp"] = gpu.temperature
                    stats["gpu_mem_used_mb"] = int(gpu.memoryUsed)
            except Exception as e:
                log.debug(f"GPUtil error: {e}")
        
        return stats
    
    # =========================================================
    #  SESSION SUMMARY
    # =========================================================
    def _build_session_summary(self) -> str:
        """Summary at end of gaming session."""
        if not self.session_start:
            return ""
        
        duration = (datetime.now() - self.session_start).total_seconds()
        mins = int(duration // 60)
        secs = int(duration % 60)
        
        parts = [f"Session: {mins}m {secs}s."]
        
        if self._cpu_samples:
            avg = sum(self._cpu_samples) / len(self._cpu_samples)
            parts.append(f"Avg CPU {avg:.0f}%.")
        
        if self._gpu_samples:
            avg = sum(self._gpu_samples) / len(self._gpu_samples)
            parts.append(f"Avg GPU {avg:.0f}%.")
        
        if self._cpu_temp_peak:
            parts.append(f"Peak CPU {self._cpu_temp_peak:.0f} deg.")
        if self._gpu_temp_peak:
            parts.append(f"Peak GPU {self._gpu_temp_peak:.0f} deg.")
        
        # Battery drain
        if self._battery_start and PSUTIL_OK:
            try:
                bat = psutil.sensors_battery()
                if bat:
                    drain = self._battery_start - int(bat.percent)
                    if drain > 0:
                        parts.append(f"Battery drained {drain}%.")
            except Exception:
                pass
        
        return " ".join(parts)

# =============================================================
#  Singleton
# =============================================================
gaming_mode = GamingMode()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- GamingMode Test ---\n")
    
    print("-- Current Stats --")
    stats = gaming_mode.get_stats()
    for k, v in stats.items():
        print(f"  {k:20} : {v}")
    
    print(f"\n  psutil: {PSUTIL_OK}")
    print(f"  GPUtil: {GPUTIL_OK}")
    
    if not GPUTIL_OK:
        print("\n[INFO] GPUtil not installed. GPU monitoring won't work.")
        print("[INFO] Install: pip install GPUtil")
    
    # Uncomment for live enter/exit test:
    # def speak(msg):
    #     print(f"  [SPEAK] {msg}")
    # 
    # mode_manager.switch(Mode.GAMING)
    # gaming_mode.enter(on_speak=speak)
    # print("\nSimulating 10 seconds of monitoring...")
    # time.sleep(10)
    # gaming_mode.exit(on_speak=speak)
    # mode_manager.switch(Mode.NEURAL)
    
    print("\n[OK] GamingMode test complete\n")