# ═════════════════════════════════════════════════════════════
#  Backend/Utils/PathResolver.py  —  Smart Path Detection
#
#  Kya karta:
#    - Jarvis root folder auto-detect karta
#    - App paths find karta (VS Code, Chrome, Spotify, WhatsApp)
#    - Chrome profiles list karta (Deep, Risky, JarvisAI)
#    - User directories resolve karta (Downloads, Desktop, etc.)
#    - Memory/Data/Logs paths centralized deta
#
#  Usage:
#    from Backend.Utils.PathResolver import paths
#    paths.ROOT           → JARVIS_V2/
#    paths.MEMORIES_DIR   → JARVIS_V2/Memories/
#    paths.find_app("vscode")  → Full path or None
#    paths.chrome_profiles()   → ["Default", "Profile 1", ...]
# ═════════════════════════════════════════════════════════════

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Optional, List

# ── Project Root Detection ────────────────────────────────────
_THIS_FILE = Path(__file__).resolve()
ROOT = _THIS_FILE.parent.parent.parent.absolute()   # JARVIS_V2/

# ── Well-Known Directories ────────────────────────────────────
BACKEND_DIR   = ROOT / "Backend"
FRONTEND_DIR  = ROOT / "Frontend"
DATA_DIR      = ROOT / "Data"
MEMORIES_DIR  = ROOT / "Memories"
LOGS_DIR      = ROOT / "Logs"

IMAGES_DIR       = DATA_DIR / "Images"
SCREENSHOTS_DIR  = DATA_DIR / "Screenshots"
RECORDINGS_DIR   = DATA_DIR / "Recordings"
CACHE_DIR        = DATA_DIR / "Cache"
SELFEDITS_DIR    = DATA_DIR / "SelfEdits"

SOUNDS_DIR  = FRONTEND_DIR / "Sounds"
ASSETS_DIR  = FRONTEND_DIR / "Assets"

# ── Ensure directories exist ──────────────────────────────────
for _d in [DATA_DIR, MEMORIES_DIR, LOGS_DIR, IMAGES_DIR,
           SCREENSHOTS_DIR, RECORDINGS_DIR, CACHE_DIR, SELFEDITS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── Windows User Dirs ─────────────────────────────────────────
_USER_HOME     = Path.home()
_USERNAME      = os.environ.get("USERNAME", "deepl")
_LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", str(_USER_HOME / "AppData/Local")))
_ROAMING       = Path(os.environ.get("APPDATA", str(_USER_HOME / "AppData/Roaming")))
_PROGRAM_FILES   = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
_PROGRAM_FILES86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))

# ── Common user paths ─────────────────────────────────────────
DOWNLOADS_DIR = _USER_HOME / "Downloads"
DESKTOP_DIR   = _USER_HOME / "Desktop"
PICTURES_DIR  = _USER_HOME / "Pictures"
DOCUMENTS_DIR = _USER_HOME / "Documents"

# OneDrive detection (Windows often moves Desktop there)
ONEDRIVE_DIR = _USER_HOME / "OneDrive"
if ONEDRIVE_DIR.exists():
    onedrive_desktop = ONEDRIVE_DIR / "Desktop"
    if onedrive_desktop.exists():
        DESKTOP_DIR = onedrive_desktop

# ── App Detection ─────────────────────────────────────────────
_APP_CANDIDATES = {
    "vscode": [
        _LOCAL_APPDATA / "Programs" / "Microsoft VS Code" / "Code.exe",
        _PROGRAM_FILES / "Microsoft VS Code" / "Code.exe",
        _PROGRAM_FILES86 / "Microsoft VS Code" / "Code.exe",
    ],
    "chrome": [
        _PROGRAM_FILES / "Google" / "Chrome" / "Application" / "chrome.exe",
        _PROGRAM_FILES86 / "Google" / "Chrome" / "Application" / "chrome.exe",
        _LOCAL_APPDATA / "Google" / "Chrome" / "Application" / "chrome.exe",
    ],
    "spotify": [
        _ROAMING / "Spotify" / "Spotify.exe",
        _LOCAL_APPDATA / "Microsoft" / "WindowsApps" / "Spotify.exe",
    ],
    "whatsapp": [
        _LOCAL_APPDATA / "WhatsApp" / "WhatsApp.exe",
        _LOCAL_APPDATA / "Microsoft" / "WindowsApps" / "WhatsApp.exe",
    ],
    "discord": [
        _LOCAL_APPDATA / "Discord" / "app-1.0.9175" / "Discord.exe",  # version varies
        _LOCAL_APPDATA / "Discord" / "Update.exe",
    ],
    "telegram": [
        _ROAMING / "Telegram Desktop" / "Telegram.exe",
    ],
    "notepad": [
        Path("C:/Windows/System32/notepad.exe"),
        Path("C:/Windows/notepad.exe"),
    ],
    "cmd": [
        Path("C:/Windows/System32/cmd.exe"),
    ],
    "explorer": [
        Path("C:/Windows/explorer.exe"),
    ],
}

# ── Chrome User Data Dir ──────────────────────────────────────
CHROME_USER_DATA = _LOCAL_APPDATA / "Google" / "Chrome" / "User Data"

# ── Paths Class ───────────────────────────────────────────────
class Paths:
    """
    Centralized path resolver for Jarvis.
    
    Access:
        from Backend.Utils.PathResolver import paths
        paths.ROOT
        paths.MEMORIES_DIR
        paths.find_app("vscode")
        paths.chrome_profiles()
    """
    
    # ── Folder constants ──
    ROOT            = ROOT
    BACKEND_DIR     = BACKEND_DIR
    FRONTEND_DIR    = FRONTEND_DIR
    DATA_DIR        = DATA_DIR
    MEMORIES_DIR    = MEMORIES_DIR
    LOGS_DIR        = LOGS_DIR
    IMAGES_DIR      = IMAGES_DIR
    SCREENSHOTS_DIR = SCREENSHOTS_DIR
    RECORDINGS_DIR  = RECORDINGS_DIR
    CACHE_DIR       = CACHE_DIR
    SELFEDITS_DIR   = SELFEDITS_DIR
    SOUNDS_DIR      = SOUNDS_DIR
    ASSETS_DIR      = ASSETS_DIR
    
    # ── User dirs ──
    USER_HOME     = _USER_HOME
    DOWNLOADS_DIR = DOWNLOADS_DIR
    DESKTOP_DIR   = DESKTOP_DIR
    PICTURES_DIR  = PICTURES_DIR
    DOCUMENTS_DIR = DOCUMENTS_DIR
    
    # ── Specific files ──
    ENV_FILE  = ROOT / ".env"
    CHAT_LOG  = DATA_DIR / "ChatLog.json"
    
    LONG_TERM_MEM = MEMORIES_DIR / "long_term.json"
    PERSONALITY   = MEMORIES_DIR / "personality.json"
    CONTEXT       = MEMORIES_DIR / "context.json"
    EQ_LEARNED    = MEMORIES_DIR / "eq_learned.json"
    EMOTIONS      = MEMORIES_DIR / "emotions.json"
    COMPANION_VAULT = MEMORIES_DIR / "companion_vault.json"
    COMPANION_LINES = MEMORIES_DIR / "companion_lines.json"
    GOALS_FILE      = MEMORIES_DIR / "goals.json"
    WHATSAPP_CONTACTS = MEMORIES_DIR / "whatsapp_contacts.json"
    
    # ── Chrome specific ──
    CHROME_USER_DATA = CHROME_USER_DATA
    
    @staticmethod
    def find_app(app_name: str) -> Optional[str]:
        """
        Find app executable path.
        Tries: candidate paths → PATH env → shutil.which
        Returns full path as string or None.
        """
        app_name = app_name.lower().strip()
        
        # Check candidate paths
        candidates = _APP_CANDIDATES.get(app_name, [])
        for path in candidates:
            if path.exists():
                return str(path)
        
        # Try shutil.which (PATH lookup)
        resolved = shutil.which(app_name)
        if resolved:
            return resolved
        
        # Try with .exe suffix
        resolved = shutil.which(f"{app_name}.exe")
        if resolved:
            return resolved
        
        return None
    
    @staticmethod
    def chrome_profiles() -> List[str]:
        """
        List Chrome profile folder names (e.g. ['Default', 'Profile 1']).
        Returns empty list if Chrome User Data not found.
        """
        if not CHROME_USER_DATA.exists():
            return []
        
        profiles = []
        for item in CHROME_USER_DATA.iterdir():
            if item.is_dir() and (
                item.name == "Default" or 
                item.name.startswith("Profile ") or
                item.name == "JarvisAI"
            ):
                profiles.append(item.name)
        return profiles
    
    @staticmethod
    def chrome_profile_names() -> dict:
        """
        Map profile folder → display name (from Preferences file).
        Returns {folder_name: display_name}
        Example: {"Default": "Risky", "Profile 1": "Deep", "JarvisAI": "JarvisAI"}
        """
        result = {}
        for profile_folder in Paths.chrome_profiles():
            prefs_file = CHROME_USER_DATA / profile_folder / "Preferences"
            if prefs_file.exists():
                try:
                    with open(prefs_file, "r", encoding="utf-8") as f:
                        prefs = json.load(f)
                    name = prefs.get("profile", {}).get("name", profile_folder)
                    result[profile_folder] = name
                except Exception:
                    result[profile_folder] = profile_folder
            else:
                result[profile_folder] = profile_folder
        return result
    
    @staticmethod
    def memories_path(filename: str) -> Path:
        """Get path to a file in Memories/ folder."""
        return MEMORIES_DIR / filename
    
    @staticmethod
    def data_path(filename: str) -> Path:
        """Get path to a file in Data/ folder."""
        return DATA_DIR / filename
    
    @staticmethod
    def logs_path(filename: str) -> Path:
        """Get path to a file in Logs/ folder."""
        return LOGS_DIR / filename

# ── Singleton instance ────────────────────────────────────────
paths = Paths()

# ── Test block ────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n─── PathResolver Test ───\n")
    
    print(f"Project ROOT     : {paths.ROOT}")
    print(f"Backend          : {paths.BACKEND_DIR}")
    print(f"Memories         : {paths.MEMORIES_DIR}")
    print(f"Logs             : {paths.LOGS_DIR}")
    print(f"User Home        : {paths.USER_HOME}")
    print(f"Downloads        : {paths.DOWNLOADS_DIR}")
    print(f"Desktop          : {paths.DESKTOP_DIR}")
    print()
    
    print("── App Detection ──")
    for app in ["vscode", "chrome", "spotify", "whatsapp", "notepad", "discord"]:
        path = paths.find_app(app)
        status = f"✓ {path}" if path else "✗ Not found"
        print(f"  {app:12} : {status}")
    
    print("\n── Chrome Profiles ──")
    profiles = paths.chrome_profile_names()
    if profiles:
        for folder, name in profiles.items():
            print(f"  {folder:15} → {name}")
    else:
        print("  No Chrome profiles found.")
    
    print("\n── Memory Files ──")
    print(f"  long_term    : {paths.LONG_TERM_MEM.exists()}  ({paths.LONG_TERM_MEM})")
    print(f"  personality  : {paths.PERSONALITY.exists()}  ({paths.PERSONALITY})")
    print(f"  companion    : {paths.COMPANION_VAULT.exists()}  ({paths.COMPANION_VAULT})")
    
    print("\n✓ PathResolver test complete\n")