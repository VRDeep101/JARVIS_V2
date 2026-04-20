# =============================================================
#  Backend/Core/SelfEditor.py - Safe Self-Adaptation
#
#  Kya karta:
#    - Jarvis apne code ko safely edit kar sakta
#    - Backup before every change (.bak file)
#    - Syntax check (ast.parse) - rollback if broken
#    - Restricted to safe files only (protected list)
#    - Log every change to Logs/self_edits.log
#    - Diff tracker (what changed)
#    - Undo last edit command
#
#  SAFE edits allowed:
#    - Add STT misrecognitions
#    - Add new loading phrases
#    - Add app aliases
#    - Add learned user patterns
#
#  PROTECTED files (never edit):
#    - Main.py, Router.py, ErrorHandler.py
#    - API keys (.env)
#    - Password files
#    - Companion vault
#
#  Usage:
#    from Backend.Core.SelfEditor import self_editor
#    ok = self_editor.add_stt_correction("harvis", "jarvis")
#    ok = self_editor.add_app_alias("vscode", "coder")
#    self_editor.undo_last()
# =============================================================

import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths

log = get_logger("SelfEditor")

# =============================================================
#  Protected files - NEVER auto-edit
# =============================================================
PROTECTED_FILES = {
    "Main.py",
    "Backend/Core/Router.py",
    "Backend/Core/ErrorHandler.py",
    "Backend/Core/SelfEditor.py",      # ironic
    "Backend/Core/ModeManager.py",
    "Backend/Modes/CompanionMode.py",
    ".env",
    "Memories/companion_vault.json",
    "Memories/companion_lines.json",
}

# =============================================================
#  Safe edit targets
# =============================================================
STT_FILE = paths.BACKEND_DIR / "Voice" / "PronunciationFixer.py"
APPS_FILE = paths.BACKEND_DIR / "Automation" / "AppRegistry.py"
PHRASES_FILE = paths.BACKEND_DIR / "Voice" / "LoadingPhrases.py"

# =============================================================
#  Edit log
# =============================================================
SELF_EDITS_LOG = paths.SELFEDITS_DIR / "edits_history.json"

def _load_edit_history() -> List[Dict]:
    try:
        if SELF_EDITS_LOG.exists():
            with open(SELF_EDITS_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_edit_history(history: List[Dict]):
    try:
        SELFEDITS_DIR = paths.SELFEDITS_DIR
        SELFEDITS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SELF_EDITS_LOG, "w", encoding="utf-8") as f:
            json.dump(history[-100:], f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Edit log save: {e}")

# =============================================================
#  Helpers
# =============================================================
def _is_protected(filepath: Path) -> bool:
    """Check if file is in the protected set."""
    rel = filepath.relative_to(paths.ROOT) if str(paths.ROOT) in str(filepath) else filepath
    rel_str = str(rel).replace("\\", "/")
    return any(p in rel_str for p in PROTECTED_FILES)

def _syntax_ok(code: str) -> bool:
    """Verify Python code parses."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

def _backup(filepath: Path) -> Optional[Path]:
    """Create .bak backup. Returns backup path."""
    try:
        backup_dir = paths.SELFEDITS_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filepath.stem}_{timestamp}.bak"
        backup_path = backup_dir / backup_name
        
        shutil.copy2(filepath, backup_path)
        return backup_path
    except Exception as e:
        log.error(f"Backup error: {e}")
        return None

# =============================================================
#  SelfEditor class
# =============================================================
class SelfEditor:
    """Safe code self-modification."""
    
    # =========================================================
    #  Generic safe-edit primitive
    # =========================================================
    def _safe_edit(
        self,
        filepath: Path,
        old_str: str,
        new_str: str,
        change_desc: str,
    ) -> Dict:
        """
        Perform a string replacement with safety checks.
        - Checks file not protected
        - Creates backup
        - Verifies syntax after edit
        - Logs change
        - Rolls back on failure
        """
        if not filepath.exists():
            return {"ok": False, "message": f"File not found: {filepath}"}
        
        if _is_protected(filepath):
            log.warn(f"Blocked edit attempt on protected file: {filepath}")
            return {"ok": False, "message": "File is protected from auto-edit"}
        
        # Read
        try:
            original = filepath.read_text(encoding="utf-8")
        except Exception as e:
            return {"ok": False, "message": f"Read error: {e}"}
        
        if old_str not in original:
            return {"ok": False, "message": "Target string not found in file"}
        
        # Already applied?
        if new_str in original and old_str in new_str:
            return {"ok": True, "message": "Already applied", "no_change": True}
        
        # Backup
        backup_path = _backup(filepath)
        if not backup_path:
            return {"ok": False, "message": "Could not create backup"}
        
        # Apply
        new_content = original.replace(old_str, new_str, 1)
        
        # Syntax check
        if filepath.suffix == ".py" and not _syntax_ok(new_content):
            log.error(f"Syntax broken by edit - rolling back: {filepath.name}")
            return {
                "ok": False,
                "message": "Edit would break syntax - aborted",
                "backup": str(backup_path),
            }
        
        # Write
        try:
            filepath.write_text(new_content, encoding="utf-8")
        except Exception as e:
            # Restore from backup
            shutil.copy2(backup_path, filepath)
            return {"ok": False, "message": f"Write failed, restored: {e}"}
        
        # Log the edit
        log.self_edit(str(filepath.relative_to(paths.ROOT)), change_desc)
        
        history = _load_edit_history()
        history.append({
            "timestamp": datetime.now().isoformat(),
            "file": str(filepath.relative_to(paths.ROOT)),
            "description": change_desc,
            "backup": str(backup_path),
            "old_snippet": old_str[:100],
            "new_snippet": new_str[:100],
        })
        _save_edit_history(history)
        
        return {
            "ok": True,
            "message": f"Updated: {change_desc}",
            "backup": str(backup_path),
            "file": str(filepath.relative_to(paths.ROOT)),
        }
    
    # =========================================================
    #  SPECIFIC SAFE EDITS
    # =========================================================
    
    def add_stt_correction(self, wrong: str, right: str) -> Dict:
        """
        Add a new STT auto-correction.
        e.g. "harvis" -> "jarvis"
        
        Modifies STT_CORRECTIONS dict in PronunciationFixer.py
        """
        wrong = wrong.strip().lower()
        right = right.strip().lower()
        
        if not wrong or not right:
            return {"ok": False, "message": "Both wrong and right strings needed"}
        
        if len(wrong) < 2 or len(right) < 2:
            return {"ok": False, "message": "Strings too short"}
        
        # Read file - check if already present
        try:
            content = STT_FILE.read_text(encoding="utf-8")
        except Exception as e:
            return {"ok": False, "message": f"Read error: {e}"}
        
        if f'"{wrong}": "{right}"' in content:
            return {"ok": True, "message": "Already present", "no_change": True}
        
        # Find the closing of STT_CORRECTIONS dict
        marker_old = "    # Common Deep-related"
        marker_new = f'    "{wrong}": "{right}",\n    # Common Deep-related'
        
        if marker_old not in content:
            # Fallback: find closing brace
            marker_old = "}\n\ndef correct_stt_text"
            marker_new = f'    "{wrong}": "{right}",\n{marker_old}'
        
        return self._safe_edit(
            STT_FILE,
            old_str=marker_old,
            new_str=marker_new,
            change_desc=f"Added STT correction: {wrong} -> {right}",
        )
    
    def add_loading_phrase(self, category: str, phrase: str) -> Dict:
        """Add a new loading phrase to a category."""
        category = category.strip().lower()
        phrase = phrase.strip()
        
        if not category or not phrase or len(phrase) < 3:
            return {"ok": False, "message": "Need valid category and phrase"}
        
        # Escape for Python string
        escaped = phrase.replace('"', '\\"')
        
        try:
            content = PHRASES_FILE.read_text(encoding="utf-8")
        except Exception as e:
            return {"ok": False, "message": f"Read error: {e}"}
        
        # Find the category list
        pattern = rf'"{category}":\s*\['
        match = re.search(pattern, content)
        if not match:
            return {"ok": False, "message": f"Category '{category}' not found"}
        
        # Check if already present
        if f'"{phrase}"' in content or f"'{phrase}'" in content:
            return {"ok": True, "message": "Already present", "no_change": True}
        
        # Find end of that list to add before it
        start_idx = match.end()
        list_depth = 1
        i = start_idx
        while i < len(content) and list_depth > 0:
            if content[i] == "[":
                list_depth += 1
            elif content[i] == "]":
                list_depth -= 1
                if list_depth == 0:
                    break
            i += 1
        
        if list_depth != 0:
            return {"ok": False, "message": "Could not find category end"}
        
        # Insert phrase before closing ]
        # Find last ", to position after it
        before_close = content[:i].rstrip()
        if before_close.endswith(","):
            new_line = f'\n        "{escaped}",'
        else:
            new_line = f',\n        "{escaped}"'
        
        old_str = content[start_idx:i+1]
        new_str = content[start_idx:i] + new_line + "\n    ]"
        new_str = new_str[:-1]  # drop extra ]
        
        # Simpler alternative: just find "],\n" closing pattern after our category
        # and inject before it
        
        # --- Safer approach: insert right after '['
        # find the [ after "category":
        bracket_pos = content.find("[", match.start())
        if bracket_pos == -1:
            return {"ok": False, "message": "Malformed category"}
        
        old_snippet = content[match.start():bracket_pos+1]
        new_snippet = old_snippet + f'\n        "{escaped}",'
        
        return self._safe_edit(
            PHRASES_FILE,
            old_str=old_snippet,
            new_str=new_snippet,
            change_desc=f"Added phrase to '{category}': {phrase[:40]}",
        )
    
    def add_app_alias(self, app_name: str, alias: str) -> Dict:
        """Add a new alias to an existing app in AppRegistry."""
        app_name = app_name.strip().lower()
        alias = alias.strip().lower()
        
        if not app_name or not alias:
            return {"ok": False, "message": "Need app name and alias"}
        
        try:
            content = APPS_FILE.read_text(encoding="utf-8")
        except Exception as e:
            return {"ok": False, "message": f"Read error: {e}"}
        
        # Find app block
        app_pattern = rf'"{app_name}":\s*\{{'
        match = re.search(app_pattern, content)
        if not match:
            return {"ok": False, "message": f"App '{app_name}' not found"}
        
        # Find alt_names within this app's block
        block_start = match.end()
        brace_depth = 1
        i = block_start
        while i < len(content) and brace_depth > 0:
            if content[i] == "{":
                brace_depth += 1
            elif content[i] == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    break
            i += 1
        
        block = content[block_start:i]
        
        # Check if already in alt_names
        if f'"{alias}"' in block:
            return {"ok": True, "message": "Alias already present", "no_change": True}
        
        # Find alt_names list within block
        alt_pattern = r'"alt_names":\s*\[([^\]]*)\]'
        alt_match = re.search(alt_pattern, block)
        if not alt_match:
            return {"ok": False, "message": "alt_names field not found"}
        
        old_alt = alt_match.group(0)
        alt_list_content = alt_match.group(1).strip()
        if alt_list_content:
            new_alt = f'"alt_names": [{alt_list_content}, "{alias}"]'
        else:
            new_alt = f'"alt_names": ["{alias}"]'
        
        return self._safe_edit(
            APPS_FILE,
            old_str=old_alt,
            new_str=new_alt,
            change_desc=f"Added alias '{alias}' for app '{app_name}'",
        )
    
    # =========================================================
    #  HISTORY / UNDO
    # =========================================================
    def list_edits(self, limit: int = 10) -> List[Dict]:
        """Last N self-edits."""
        history = _load_edit_history()
        return history[-limit:]
    
    def undo_last(self) -> Dict:
        """Restore most recent edit from backup."""
        history = _load_edit_history()
        if not history:
            return {"ok": False, "message": "No edits to undo"}
        
        last = history[-1]
        backup_path = Path(last.get("backup", ""))
        file_path = paths.ROOT / last.get("file", "")
        
        if not backup_path.exists():
            return {"ok": False, "message": "Backup file missing"}
        if not file_path.exists():
            return {"ok": False, "message": "Target file missing"}
        
        try:
            shutil.copy2(backup_path, file_path)
            history.pop()
            _save_edit_history(history)
            log.info(f"Undid edit: {last.get('description')}")
            return {
                "ok": True,
                "message": f"Reverted: {last.get('description')}",
            }
        except Exception as e:
            return {"ok": False, "message": f"Undo failed: {e}"}

# =============================================================
#  Singleton
# =============================================================
self_editor = SelfEditor()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- SelfEditor Test ---\n")
    
    print("-- Protection check --")
    main_py = paths.ROOT / "Main.py"
    router = paths.BACKEND_DIR / "Core" / "Router.py"
    phrases = paths.BACKEND_DIR / "Voice" / "LoadingPhrases.py"
    
    print(f"  Main.py protected         : {_is_protected(main_py)}")
    print(f"  Router.py protected       : {_is_protected(router)}")
    print(f"  LoadingPhrases.py protected: {_is_protected(phrases)}")
    
    print("\n-- Edit history --")
    edits = self_editor.list_edits()
    print(f"  Total edits on record: {len(edits)}")
    for e in edits[-3:]:
        print(f"  - {e.get('description')}")
    
    # Uncomment to test live (will actually modify files):
    # print("\n-- Live test: add STT correction --")
    # r = self_editor.add_stt_correction("jervis", "jarvis")
    # print(f"  {r}")
    # 
    # print("\n-- Live test: add loading