# =============================================================
#  Backend/Modes/ScanningMode.py - System/Network Scans
#
#  Kya karta:
#    - WiFi scan (nearby networks via netsh)
#    - Bluetooth devices list (paired + discoverable)
#    - System scan (CPU/RAM/disk/processes - top 10)
#    - Port scan (localhost common ports)
#    - Network scan (LAN devices via ARP)
#
#  Usage:
#    from Backend.Modes.ScanningMode import scanning_mode
#    scanning_mode.enter(on_speak=tts_cb)
#    result = scanning_mode.scan_wifi()
#    result = scanning_mode.scan_system()
# =============================================================

import re
import socket
import subprocess
from typing import Callable, Dict, List, Optional

from Backend.Utils.Logger import get_logger
from Backend.Core.ModeManager import mode_manager, Mode

log = get_logger("ScanningMode")

try:
    import psutil
    PSUTIL_OK = True
except Exception:
    PSUTIL_OK = False

# =============================================================
#  ScanningMode class
# =============================================================
class ScanningMode:
    """Active scanning toolkit."""
    
    def __init__(self):
        self.active = False
        self.on_speak: Optional[Callable] = None
    
    # =========================================================
    #  Enter / Exit
    # =========================================================
    def enter(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        self.active = True
        self.on_speak = on_speak
        announce = mode_manager.current_info["voice_announce"]
        log.info("Scanning mode entered")
        if on_speak:
            on_speak(announce)
        return announce
    
    def exit(self, on_speak: Optional[Callable[[str], None]] = None) -> str:
        self.active = False
        log.info("Scanning mode exited")
        msg = "Scanning mode deactivated, Sir."
        if on_speak:
            on_speak(msg)
        return msg
    
    def is_active(self) -> bool:
        return self.active and mode_manager.current_mode == Mode.SCANNING
    
    # =========================================================
    #  WIFI SCAN
    # =========================================================
    def scan_wifi(self) -> Dict:
        """List nearby WiFi networks via netsh."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True, text=True, timeout=15, encoding="utf-8", errors="ignore",
            )
            if result.returncode != 0:
                return {
                    "ok": False,
                    "message": "WiFi scan failed. Check WiFi is on, Sir.",
                }
            
            output = result.stdout
            networks = []
            current = {}
            
            for line in output.splitlines():
                line = line.strip()
                
                m = re.match(r"^SSID\s+\d+\s*:\s*(.+)$", line)
                if m:
                    if current:
                        networks.append(current)
                    current = {"ssid": m.group(1).strip()}
                    continue
                
                m = re.match(r"^Authentication\s*:\s*(.+)$", line)
                if m and current:
                    current["security"] = m.group(1).strip()
                    continue
                
                m = re.match(r"^Signal\s*:\s*(.+)$", line)
                if m and current:
                    current["signal"] = m.group(1).strip()
                    continue
                
                m = re.match(r"^BSSID\s+\d+\s*:\s*(.+)$", line)
                if m and current and "bssid" not in current:
                    current["bssid"] = m.group(1).strip()
            
            if current:
                networks.append(current)
            
            # Filter: keep only ones with SSID
            networks = [n for n in networks if n.get("ssid")]
            
            summary = self._summarize_wifi(networks)
            
            log.info(f"WiFi scan: {len(networks)} networks found")
            return {
                "ok": True,
                "count": len(networks),
                "networks": networks,
                "summary": summary,
                "message": summary,
            }
        except FileNotFoundError:
            return {"ok": False, "message": "netsh not available (not Windows?)"}
        except Exception as e:
            log.error(f"WiFi scan error: {e}")
            return {"ok": False, "message": f"Scan failed: {str(e)[:60]}"}
    
    def _summarize_wifi(self, networks: List[Dict]) -> str:
        """Make a spoken-friendly summary."""
        if not networks:
            return "No WiFi networks detected, Sir."
        
        # Sort by signal strength
        def signal_val(n):
            s = n.get("signal", "0%").replace("%", "")
            try:
                return int(s)
            except Exception:
                return 0
        
        networks.sort(key=signal_val, reverse=True)
        
        open_count = sum(1 for n in networks if n.get("security", "").lower() == "open")
        
        lines = [f"Found {len(networks)} networks, Sir."]
        if open_count:
            lines.append(f"{open_count} are unsecured.")
        
        # Top 3
        lines.append("Strongest signals:")
        for n in networks[:3]:
            sec = n.get("security", "?")
            lines.append(f"- {n.get('ssid')} ({n.get('signal', '?')}, {sec})")
        
        return " ".join(lines)
    
    # =========================================================
    #  BLUETOOTH SCAN
    # =========================================================
    def scan_bluetooth(self) -> Dict:
        """List paired + known Bluetooth devices."""
        ps = (
            "Get-PnpDevice -Class Bluetooth -PresentOnly | "
            "Select-Object FriendlyName, Status | "
            "ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell", "-Command", ps],
                capture_output=True, text=True, timeout=15,
            )
            
            import json
            output = result.stdout.strip()
            if not output:
                return {
                    "ok": True,
                    "count": 0,
                    "devices": [],
                    "message": "No Bluetooth devices found, Sir.",
                }
            
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            
            devices = []
            for d in data:
                name = d.get("FriendlyName", "Unknown")
                status = d.get("Status", "")
                devices.append({"name": name, "status": status})
            
            # Filter out generic adapter entries
            meaningful = [
                d for d in devices
                if d["name"] and not d["name"].lower().startswith(("generic", "microsoft bluetooth"))
            ]
            
            msg = f"Found {len(meaningful)} Bluetooth devices, Sir."
            if meaningful:
                names = ", ".join(d["name"] for d in meaningful[:3])
                msg += f" Including: {names}."
            
            log.info(f"BT scan: {len(meaningful)} devices")
            return {
                "ok": True,
                "count": len(meaningful),
                "devices": meaningful,
                "message": msg,
            }
        except Exception as e:
            log.error(f"BT scan error: {e}")
            return {"ok": False, "message": f"Scan failed: {str(e)[:60]}"}
    
    # =========================================================
    #  SYSTEM SCAN
    # =========================================================
    def scan_system(self) -> Dict:
        """Full system snapshot."""
        if not PSUTIL_OK:
            return {"ok": False, "message": "psutil missing"}
        
        try:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            
            # Top 5 processes by CPU
            procs = []
            for p in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
                try:
                    procs.append({
                        "name": p.info["name"],
                        "cpu": p.info["cpu_percent"] or 0,
                        "mem": round(p.info["memory_percent"] or 0, 1),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            procs.sort(key=lambda x: x["cpu"], reverse=True)
            top5 = procs[:5]
            
            # Battery
            battery = None
            try:
                bat = psutil.sensors_battery()
                if bat:
                    battery = {
                        "percent": int(bat.percent),
                        "plugged": bat.power_plugged,
                    }
            except Exception:
                pass
            
            # Network bytes
            net_io = psutil.net_io_counters()
            
            summary = (
                f"System status, Sir: "
                f"CPU at {cpu}%, "
                f"RAM at {ram.percent}% "
                f"({round(ram.used / 1024**3, 1)} of {round(ram.total / 1024**3, 1)} GB used), "
                f"Disk at {disk.percent}%."
            )
            if battery:
                summary += f" Battery at {battery['percent']}%."
            
            return {
                "ok": True,
                "cpu_percent": cpu,
                "ram_percent": ram.percent,
                "ram_used_gb": round(ram.used / 1024**3, 1),
                "ram_total_gb": round(ram.total / 1024**3, 1),
                "disk_percent": disk.percent,
                "battery": battery,
                "top_processes": top5,
                "net_sent_mb": round(net_io.bytes_sent / 1024**2, 1),
                "net_recv_mb": round(net_io.bytes_recv / 1024**2, 1),
                "summary": summary,
                "message": summary,
            }
        except Exception as e:
            return {"ok": False, "message": f"Scan failed: {str(e)[:60]}"}
    
    # =========================================================
    #  PORT SCAN (localhost)
    # =========================================================
    def scan_ports(self, common_only: bool = True) -> Dict:
        """Scan localhost for open ports."""
        COMMON_PORTS = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
            53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
            443: "HTTPS", 445: "SMB", 3306: "MySQL", 3389: "RDP",
            5432: "PostgreSQL", 5900: "VNC", 6379: "Redis",
            8000: "HTTP-alt", 8080: "HTTP-alt", 8443: "HTTPS-alt",
            9876: "Jarvis STT", 27017: "MongoDB",
        }
        
        open_ports = []
        for port, service in COMMON_PORTS.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            try:
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    open_ports.append({"port": port, "service": service})
            except Exception:
                pass
            finally:
                sock.close()
        
        if open_ports:
            summary = f"Found {len(open_ports)} open ports on localhost, Sir: "
            summary += ", ".join(f"{p['port']} ({p['service']})" for p in open_ports[:5])
        else:
            summary = "No common ports open on localhost, Sir."
        
        return {
            "ok": True,
            "count": len(open_ports),
            "open_ports": open_ports,
            "message": summary,
        }
    
    # =========================================================
    #  NETWORK SCAN (LAN devices via ARP)
    # =========================================================
    def scan_network(self) -> Dict:
        """Find devices on local network via ARP table."""
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True, text=True, timeout=5, encoding="utf-8", errors="ignore",
            )
            
            devices = []
            for line in result.stdout.splitlines():
                # Match: "192.168.1.1    aa-bb-cc-dd-ee-ff    dynamic"
                m = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-:]+)\s+(\w+)", line)
                if m:
                    ip, mac, type_ = m.groups()
                    if type_.lower() == "dynamic":  # active devices
                        devices.append({"ip": ip, "mac": mac})
            
            msg = f"Found {len(devices)} active devices on your network, Sir."
            log.info(f"Network scan: {len(devices)} devices")
            
            return {
                "ok": True,
                "count": len(devices),
                "devices": devices,
                "message": msg,
            }
        except Exception as e:
            return {"ok": False, "message": f"Scan failed: {str(e)[:60]}"}
    
    # =========================================================
    #  ROUTER: pick scan based on voice query
    # =========================================================
    def run(self, query: str) -> Dict:
        """Route query to specific scan."""
        q = query.lower()
        
        if "wifi" in q or "wi-fi" in q or "wireless" in q:
            return self.scan_wifi()
        if "bluetooth" in q or "bt" in q:
            return self.scan_bluetooth()
        if "system" in q or "cpu" in q or "ram" in q or "process" in q:
            return self.scan_system()
        if "port" in q:
            return self.scan_ports()
        if "network" in q or "lan" in q or "device" in q:
            return self.scan_network()
        
        # Default: ask which
        return {
            "ok": False,
            "ask_user": True,
            "message": "What should I scan, Sir - WiFi, devices, system, or network?",
        }

# =============================================================
#  Singleton
# =============================================================
scanning_mode = ScanningMode()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- ScanningMode Test ---\n")
    
    print("-- System Scan (always works) --")
    r = scanning_mode.scan_system()
    print(f"  {r['message']}")
    if r.get("top_processes"):
        print("  Top processes:")
        for p in r["top_processes"][:3]:
            print(f"    {p['name']:25} CPU: {p['cpu']:.1f}%  MEM: {p['mem']:.1f}%")
    
    print("\n-- Port Scan (localhost) --")
    r = scanning_mode.scan_ports()
    print(f"  {r['message']}")
    
    # Uncomment for live WiFi scan (needs WiFi on):
    # print("\n-- WiFi Scan --")
    # r = scanning_mode.scan_wifi()
    # print(f"  {r['message']}")
    # if r.get("networks"):
    #     for n in r["networks"][:3]:
    #         print(f"    {n.get('ssid', '?'):25} {n.get('signal', '?')} {n.get('security', '?')}")
    
    # Uncomment for live network scan:
    # print("\n-- Network Scan --")
    # r = scanning_mode.scan_network()
    # print(f"  {r['message']}")
    
    print("\n[OK] ScanningMode test complete\n")