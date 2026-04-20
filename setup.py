# ═════════════════════════════════════════════════════════════
#  JARVIS V2 — Setup Script
#
#  Kya karta:
#    1. Saara folder structure banata
#    2. Saare __init__.py files create karta
#    3. Empty memory files initialize karta
#    4. Dependencies install karta (Requirements.txt se)
#    5. Verification check karta sab theek hai
#
#  Run: python setup.py
# ═════════════════════════════════════════════════════════════

import os
import sys
import json
import subprocess
from pathlib import Path

# ── Colors for terminal output ────────────────────────────────
class Color:
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    RED    = '\033[91m'
    BLUE   = '\033[94m'
    BOLD   = '\033[1m'
    END    = '\033[0m'

def p_ok(msg):    print(f"{Color.GREEN}✅ {msg}{Color.END}")
def p_warn(msg):  print(f"{Color.YELLOW}⚠️  {msg}{Color.END}")
def p_err(msg):   print(f"{Color.RED}❌ {msg}{Color.END}")
def p_info(msg):  print(f"{Color.BLUE}ℹ️  {msg}{Color.END}")
def p_title(msg): print(f"\n{Color.BOLD}{Color.BLUE}═══ {msg} ═══{Color.END}\n")

# ── Root path ─────────────────────────────────────────────────
ROOT = Path(__file__).parent.absolute()

# ── Folder Structure ──────────────────────────────────────────
FOLDERS = [
    # Backend
    "Backend",
    "Backend/Core",
    "Backend/Brain",
    "Backend/Voice",
    "Backend/Automation",
    "Backend/Modes",
    "Backend/External",
    "Backend/Notifications",
    "Backend/Utils",

    # Frontend
    "Frontend",
    "Frontend/Graphics",
    "Frontend/Themes",
    "Frontend/Sounds",
    "Frontend/Assets",

    # Data (clearable cache)
    "Data",
    "Data/Images",
    "Data/Screenshots",
    "Data/Recordings",
    "Data/Cache",
    "Data/SelfEdits",

    # Memories (protected)
    "Memories",

    # Logs
    "Logs",
]

# ── Init files (packages) ─────────────────────────────────────
INIT_FILES = [
    "Backend/__init__.py",
    "Backend/Core/__init__.py",
    "Backend/Brain/__init__.py",
    "Backend/Voice/__init__.py",
    "Backend/Automation/__init__.py",
    "Backend/Modes/__init__.py",
    "Backend/External/__init__.py",
    "Backend/Notifications/__init__.py",
    "Backend/Utils/__init__.py",
    "Frontend/__init__.py",
    "Frontend/Graphics/__init__.py",
    "Frontend/Themes/__init__.py",
]

# ── Initial Memory Files ──────────────────────────────────────
MEMORY_INIT = {
    "Memories/long_term.json": {
        "facts_about_user": [],
        "user_goals": [],
        "shared_memories": [],
        "preferences": {},
        "loved_things": [],
        "disliked_things": [],
        "important_people": []
    },
    "Memories/personality.json": {
        "preferred_language": "english",
        "communication_style": "friendly_with_sarcasm",
        "topics_of_interest": [],
        "dislikes": [],
        "relationship_level": "new_friend",
        "time_spent_hours": 0.0,
        "first_met": "",
        "notes": []
    },
    "Memories/context.json": {
        "current_session_start": "",
        "current_mood": "neutral",
        "recent_topics": [],
        "last_query": "",
        "queries_this_session": 0,
        "last_mode": "neural"
    },
    "Memories/eq_learned.json": {
        "learned_keywords": {},
        "user_patterns": {},
        "false_positives": [],
        "emotion_counts": {},
        "last_updated": ""
    },
    "Memories/emotions.json": {
        "mood_history": [],
        "dominant_mood": "neutral",
        "total_interactions": 0,
        "emotional_patterns": {},
        "important_moments": [],
        "last_updated": ""
    },
    "Memories/companion_vault.json": {
        "_warning": "PROTECTED — accessible only in Companion Mode",
        "sessions": [],
        "shared_secrets": [],
        "deep_memories": [],
        "companion_lines_used": [],
        "effective_lines": [],
        "ineffective_lines": []
    },
    "Memories/goals.json": {
        "active_goals": [],
        "completed_goals": [],
        "abandoned_goals": []
    },
    "Memories/whatsapp_contacts.json": {},
    "Data/ChatLog.json": [],
    "Data/notifications.json": []
}

# ── Helper Functions ──────────────────────────────────────────
def create_folders():
    p_title("Creating folder structure")
    for folder in FOLDERS:
        path = ROOT / folder
        path.mkdir(parents=True, exist_ok=True)
        p_ok(f"Folder: {folder}")

def create_init_files():
    p_title("Creating __init__.py files")
    for init_file in INIT_FILES:
        path = ROOT / init_file
        if not path.exists():
            path.touch()
        p_ok(f"Init: {init_file}")

def create_memory_files():
    p_title("Initializing memory files")
    for filepath, content in MEMORY_INIT.items():
        path = ROOT / filepath
        if path.exists() and path.stat().st_size > 10:
            p_warn(f"Exists (skipped): {filepath}")
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        p_ok(f"Created: {filepath}")

def check_env_file():
    p_title("Checking .env file")
    env_path = ROOT / ".env"
    if not env_path.exists():
        p_err(".env file NOT FOUND!")
        p_info("Please create .env file from the template I provided.")
        return False
    
    required_keys = [
        "GroqAPIKey", "CohereAPIKey", "HuggingFaceAPIKey",
        "OpenWeatherAPIKey", "NewsAPIKey", "WolframAPIKey", "GeminiAPIKey"
    ]
    
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    missing = []
    for key in required_keys:
        if f"{key}=paste_here" in content or f"{key}=" not in content:
            missing.append(key)
    
    if missing:
        p_warn(f"Missing/unset API keys: {', '.join(missing)}")
        p_info("Jarvis will still run, but some features will be disabled.")
    else:
        p_ok("All API keys appear to be set.")
    
    return True

def install_dependencies():
    p_title("Installing dependencies from Requirements.txt")
    req_path = ROOT / "Requirements.txt"
    if not req_path.exists():
        p_err("Requirements.txt not found!")
        return False
    
    try:
        p_info("This may take 5-10 minutes. Grab chai ☕")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_path)],
            capture_output=False,
            text=True
        )
        if result.returncode == 0:
            p_ok("All dependencies installed.")
            return True
        else:
            p_err("Some dependencies failed. Check errors above.")
            return False
    except Exception as e:
        p_err(f"Install error: {e}")
        return False

def verify_python_version():
    p_title("Verifying Python version")
    v = sys.version_info
    if v.major == 3 and v.minor >= 10:
        p_ok(f"Python {v.major}.{v.minor}.{v.micro} — OK")
        return True
    else:
        p_err(f"Python {v.major}.{v.minor} — NEEDS 3.10+")
        return False

def print_banner():
    banner = f"""
{Color.BLUE}{Color.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║         ░░░  JARVIS V2 — SETUP SCRIPT  ░░░                   ║
║                                                              ║
║         Alive. Adaptive. Accountable.                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Color.END}
"""
    print(banner)

def print_final_message(success):
    if success:
        print(f"""
{Color.GREEN}{Color.BOLD}
═══════════════════════════════════════════════════════════════
   ✅  SETUP COMPLETE — Ready for Phase 2
═══════════════════════════════════════════════════════════════
{Color.END}
{Color.BLUE}Next steps:
  1. Fill in any remaining API keys in .env
  2. Reply: "Phase 1 done" to get Phase 2 code
{Color.END}
""")
    else:
        print(f"""
{Color.RED}{Color.BOLD}
═══════════════════════════════════════════════════════════════
   ⚠️  SETUP INCOMPLETE — Fix errors above and re-run
═══════════════════════════════════════════════════════════════
{Color.END}
""")

# ── Main ──────────────────────────────────────────────────────
def main():
    print_banner()
    
    if not verify_python_version():
        print_final_message(False)
        return
    
    create_folders()
    create_init_files()
    create_memory_files()
    
    env_ok = check_env_file()
    
    # Ask about dependency install
    print(f"\n{Color.YELLOW}Install dependencies now? (y/n):{Color.END} ", end="")
    choice = input().strip().lower()
    
    deps_ok = True
    if choice == "y":
        deps_ok = install_dependencies()
    else:
        p_info("Skipped dependency install. Run later: pip install -r Requirements.txt")
    
    print_final_message(env_ok and deps_ok)

if __name__ == "__main__":
    main()