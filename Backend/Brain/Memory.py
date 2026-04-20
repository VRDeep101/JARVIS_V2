# =============================================================
#  Backend/Brain/Memory.py - 3-Tier Memory System
#
#  3 tiers:
#    SHORT-TERM  - current session (ContextManager handles)
#    MID-TERM    - last 3 days of facts/events
#    LONG-TERM   - permanent facts about user (never expires)
#
#  Kya karta:
#    - Facts about user save karta (name, likes, goals, people)
#    - Important people track karta (with importance score)
#    - Goals manage karta (active/completed/abandoned)
#    - Shared memories (Jarvis-Deep moments)
#    - Confidence scoring (3+ mentions = solid fact)
#    - Auto-merge duplicates
#    - Companion vault - STRICT isolation (only in Companion mode)
#    - Search by keyword
#
#  Usage:
#    from Backend.Brain.Memory import memory
#    memory.save_fact("Sir loves coding")
#    memory.save_person("Vishakha", relation="special", importance=10)
#    memory.save_goal("Build AGI", status="active")
#    memory.get_summary()  -> for LLM context
#    memory.recall("vishakha")  -> fetches related memories
# =============================================================

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Core.ModeManager import mode_manager, Mode
from Backend.Core.ErrorHandler import safe_run

log = get_logger("Memory")

# -- Paths (from PathResolver) -------------------------------
LONG_TERM_PATH     = paths.LONG_TERM_MEM
PERSONALITY_PATH   = paths.PERSONALITY
GOALS_PATH         = paths.GOALS_FILE
VAULT_PATH         = paths.COMPANION_VAULT

# -- Config ---------------------------------------------------
CONFIDENCE_THRESHOLD = 3        # mentions needed for "solid" fact
MAX_FACTS_PER_CATEGORY = 100    # cap per list
MAX_SHARED_MEMORIES = 500

# -- Default structures --------------------------------------
DEFAULT_LONG_TERM = {
    "facts_about_user": [],
    "user_goals": [],
    "shared_memories": [],
    "preferences": {},
    "loved_things": [],
    "disliked_things": [],
    "important_people": []
}

DEFAULT_PERSONALITY = {
    "preferred_language": "english",
    "communication_style": "friendly_with_sarcasm",
    "topics_of_interest": [],
    "dislikes": [],
    "relationship_level": "new_friend",
    "time_spent_hours": 0.0,
    "first_met": "",
    "notes": [],
    "last_updated": ""
}

DEFAULT_GOALS = {
    "active_goals": [],
    "completed_goals": [],
    "abandoned_goals": []
}

# -- Helpers: safe JSON read/write ---------------------------
def _load(path: Path, default: dict) -> dict:
    """Load JSON file; return default on error."""
    if not path.exists():
        return dict(default)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all default keys exist
        for k, v in default.items():
            if k not in data:
                data[k] = v
        return data
    except Exception as e:
        log.error(f"Load error {path.name}: {e}")
        return dict(default)

def _save(path: Path, data: dict) -> bool:
    """Atomic save: write to temp, rename."""
    try:
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
        return True
    except Exception as e:
        log.error(f"Save error {path.name}: {e}")
        return False

# -- Similarity check (avoid duplicates) ---------------------
def _similar(a: str, b: str, threshold: float = 0.75) -> bool:
    """Simple token overlap similarity."""
    if not a or not b:
        return False
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return False
    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return (overlap / union) >= threshold if union else False

# -- MemoryManager class -------------------------------------
class MemoryManager:
    """3-tier memory: long-term + personality + goals + vault."""
    
    def __init__(self):
        self.long_term = _load(LONG_TERM_PATH, DEFAULT_LONG_TERM)
        self.personality = _load(PERSONALITY_PATH, DEFAULT_PERSONALITY)
        self.goals = _load(GOALS_PATH, DEFAULT_GOALS)
        
        # Initialize first_met if missing
        if not self.personality.get("first_met"):
            self.personality["first_met"] = datetime.now().strftime("%Y-%m-%d")
            self._save_personality()
    
    # -- Save/Load wrappers -----------------------------------
    def _save_long_term(self):
        _save(LONG_TERM_PATH, self.long_term)
    
    def _save_personality(self):
        self.personality["last_updated"] = datetime.now().isoformat()
        _save(PERSONALITY_PATH, self.personality)
    
    def _save_goals(self):
        _save(GOALS_PATH, self.goals)
    
    # -- FACTS ABOUT USER -------------------------------------
    def save_fact(self, fact: str, category: str = "general", confidence: int = 1) -> bool:
        """
        Save a fact about the user.
        Handles duplicates (merges with existing).
        """
        if not fact or len(fact.strip()) < 3:
            return False
        
        fact = fact.strip()
        facts = self.long_term.get("facts_about_user", [])
        
        # Check for duplicates
        for existing in facts:
            existing_text = existing.get("fact", "") if isinstance(existing, dict) else existing
            if _similar(existing_text, fact):
                # Boost confidence of existing
                if isinstance(existing, dict):
                    existing["confidence"] = min(10, existing.get("confidence", 1) + confidence)
                    existing["last_mentioned"] = datetime.now().isoformat()
                log.debug(f"Boosted fact: '{fact[:40]}'")
                self._save_long_term()
                return True
        
        # New fact
        entry = {
            "fact": fact,
            "category": category,
            "confidence": confidence,
            "first_mentioned": datetime.now().isoformat(),
            "last_mentioned": datetime.now().isoformat(),
        }
        facts.append(entry)
        
        # Cap size
        if len(facts) > MAX_FACTS_PER_CATEGORY:
            # Remove lowest confidence old facts
            facts.sort(key=lambda x: (
                x.get("confidence", 1) if isinstance(x, dict) else 1,
                x.get("last_mentioned", "") if isinstance(x, dict) else ""
            ), reverse=True)
            facts = facts[:MAX_FACTS_PER_CATEGORY]
        
        self.long_term["facts_about_user"] = facts
        self._save_long_term()
        log.info(f"Fact saved: '{fact[:50]}'")
        return True
    
    def get_facts(self, category: Optional[str] = None, min_confidence: int = 1) -> List[Dict]:
        """Get all facts, optionally filtered."""
        facts = self.long_term.get("facts_about_user", [])
        result = []
        for f in facts:
            if isinstance(f, dict):
                if category and f.get("category") != category:
                    continue
                if f.get("confidence", 1) < min_confidence:
                    continue
                result.append(f)
            else:
                # String-format legacy fact
                if not category and min_confidence <= 1:
                    result.append({"fact": f, "confidence": 1})
        return result
    
    # -- IMPORTANT PEOPLE -------------------------------------
    def save_person(
        self, name: str,
        relation: str = "acquaintance",
        importance: int = 5,
        notes: str = "",
        attributes: dict = None,
    ) -> bool:
        """
        Save or update info about a person.
        
        importance: 1-10 (10 = extremely important, like Vishakha)
        relation: friend / family / crush / best_friend / special / colleague
        """
        if not name or len(name.strip()) < 2:
            return False
        
        name = name.strip().title()
        people = self.long_term.get("important_people", [])
        
        # Find existing
        for p in people:
            if isinstance(p, dict) and p.get("name", "").lower() == name.lower():
                # Update existing
                p["importance"] = max(p.get("importance", 5), importance)
                if relation and relation != "acquaintance":
                    p["relation"] = relation
                if notes:
                    existing_notes = p.get("notes", "")
                    if notes not in existing_notes:
                        p["notes"] = f"{existing_notes}. {notes}".strip(". ")
                if attributes:
                    p.setdefault("attributes", {}).update(attributes)
                p["last_mentioned"] = datetime.now().isoformat()
                self._save_long_term()
                log.info(f"Updated person: {name}")
                return True
        
        # New person
        entry = {
            "name": name,
            "relation": relation,
            "importance": importance,
            "notes": notes,
            "attributes": attributes or {},
            "first_mentioned": datetime.now().isoformat(),
            "last_mentioned": datetime.now().isoformat(),
        }
        people.append(entry)
        self.long_term["important_people"] = people
        self._save_long_term()
        log.info(f"New person saved: {name} (importance: {importance})")
        return True
    
    def get_person(self, name: str) -> Optional[Dict]:
        """Find person by name."""
        name_lower = name.lower().strip()
        for p in self.long_term.get("important_people", []):
            if isinstance(p, dict) and p.get("name", "").lower() == name_lower:
                return p
        return None
    
    def get_important_people(self, min_importance: int = 7) -> List[Dict]:
        """Get top-importance people."""
        people = self.long_term.get("important_people", [])
        valid = [p for p in people if isinstance(p, dict)]
        valid.sort(key=lambda p: p.get("importance", 0), reverse=True)
        return [p for p in valid if p.get("importance", 0) >= min_importance]
    
    # -- GOALS ------------------------------------------------
    def save_goal(self, goal: str, status: str = "active", notes: str = "") -> bool:
        """Save a user goal."""
        if not goal or len(goal.strip()) < 5:
            return False
        
        goal = goal.strip()
        key = f"{status}_goals"
        
        if key not in self.goals:
            self.goals[key] = []
        
        # Check duplicate
        for g in self.goals[key]:
            if isinstance(g, dict) and _similar(g.get("goal", ""), goal):
                g["last_mentioned"] = datetime.now().isoformat()
                self._save_goals()
                return True
        
        entry = {
            "goal": goal,
            "notes": notes,
            "created": datetime.now().isoformat(),
            "last_mentioned": datetime.now().isoformat(),
        }
        self.goals[key].append(entry)
        self._save_goals()
        log.info(f"Goal [{status}] saved: '{goal[:50]}'")
        return True
    
    def get_goals(self, status: str = "active") -> List[Dict]:
        """Get goals by status."""
        return self.goals.get(f"{status}_goals", [])
    
    def complete_goal(self, goal_text: str) -> bool:
        """Move goal from active to completed."""
        active = self.goals.get("active_goals", [])
        completed = self.goals.setdefault("completed_goals", [])
        
        for i, g in enumerate(active):
            text = g.get("goal", "") if isinstance(g, dict) else g
            if _similar(text, goal_text):
                goal_obj = active.pop(i)
                if isinstance(goal_obj, dict):
                    goal_obj["completed_at"] = datetime.now().isoformat()
                completed.append(goal_obj)
                self._save_goals()
                log.info(f"Goal completed: '{text[:50]}'")
                return True
        return False
    
    # -- LIKED / DISLIKED -------------------------------------
    def save_liked(self, thing: str, confidence: int = 1) -> bool:
        return self._save_to_list("loved_things", thing, confidence)
    
    def save_disliked(self, thing: str, confidence: int = 1) -> bool:
        return self._save_to_list("disliked_things", thing, confidence)
    
    def _save_to_list(self, key: str, thing: str, confidence: int) -> bool:
        """Helper: save liked/disliked items."""
        if not thing or len(thing.strip()) < 2:
            return False
        
        thing = thing.strip().lower()
        items = self.long_term.get(key, [])
        
        for item in items:
            existing = item.get("thing", "") if isinstance(item, dict) else item
            if _similar(existing, thing):
                if isinstance(item, dict):
                    item["confidence"] = min(10, item.get("confidence", 1) + confidence)
                    item["last_mentioned"] = datetime.now().isoformat()
                self._save_long_term()
                return True
        
        entry = {
            "thing": thing,
            "confidence": confidence,
            "first_mentioned": datetime.now().isoformat(),
            "last_mentioned": datetime.now().isoformat(),
        }
        items.append(entry)
        self.long_term[key] = items
        self._save_long_term()
        return True
    
    # -- SHARED MEMORIES (Jarvis-Deep moments) ----------------
    def save_shared_memory(self, memory: str, importance: int = 5) -> bool:
        """
        Save a moment between Jarvis & Deep (e.g., 'Deep fixed me at 2 AM').
        Used in Companion Mode to reference.
        """
        if not memory:
            return False
        
        entry = {
            "memory": memory.strip(),
            "importance": importance,
            "date": datetime.now().isoformat(),
        }
        mems = self.long_term.get("shared_memories", [])
        
        # Dedupe
        for m in mems:
            if isinstance(m, dict) and _similar(m.get("memory", ""), memory):
                return False
        
        mems.append(entry)
        if len(mems) > MAX_SHARED_MEMORIES:
            mems = mems[-MAX_SHARED_MEMORIES:]
        self.long_term["shared_memories"] = mems
        self._save_long_term()
        log.info(f"Shared memory saved: '{memory[:50]}'")
        return True
    
    def get_shared_memories(self, limit: int = 10) -> List[Dict]:
        """Get recent shared memories (for Companion Mode references)."""
        mems = self.long_term.get("shared_memories", [])
        valid = [m for m in mems if isinstance(m, dict)]
        valid.sort(key=lambda m: m.get("date", ""), reverse=True)
        return valid[:limit]
    
    # -- PERSONALITY / RELATIONSHIP ---------------------------
    def add_time_spent(self, minutes: float):
        """Track time spent with user."""
        hours = minutes / 60.0
        self.personality["time_spent_hours"] = round(
            self.personality.get("time_spent_hours", 0.0) + hours, 2
        )
        self._save_personality()
    
    def upgrade_relationship(self):
        """Progress the Jarvis-user relationship based on time spent."""
        hours = self.personality.get("time_spent_hours", 0.0)
        current = self.personality.get("relationship_level", "new_friend")
        
        levels = {
            "new_friend": 0,
            "friend": 2,
            "close_friend": 10,
            "best_friend": 50,
            "family": 200,
        }
        
        new_level = current
        for lvl, threshold in levels.items():
            if hours >= threshold:
                new_level = lvl
        
        if new_level != current:
            self.personality["relationship_level"] = new_level
            self._save_personality()
            log.info(f"Relationship upgraded: {current} -> {new_level}")
    
    # -- RECALL / SEARCH --------------------------------------
    def recall(self, keyword: str, limit: int = 5) -> List[Dict]:
        """Search across all memories for keyword."""
        if not keyword:
            return []
        kw = keyword.lower().strip()
        results = []
        
        # Facts
        for f in self.long_term.get("facts_about_user", []):
            text = f.get("fact", "") if isinstance(f, dict) else f
            if kw in text.lower():
                results.append({"type": "fact", "content": text,
                                "data": f if isinstance(f, dict) else None})
        
        # People
        for p in self.long_term.get("important_people", []):
            if isinstance(p, dict):
                if kw in p.get("name", "").lower() or kw in p.get("notes", "").lower():
                    results.append({"type": "person", "content": p.get("name"),
                                    "data": p})
        
        # Goals
        for status in ["active", "completed"]:
            for g in self.goals.get(f"{status}_goals", []):
                text = g.get("goal", "") if isinstance(g, dict) else g
                if kw in text.lower():
                    results.append({"type": "goal", "content": text,
                                    "data": g if isinstance(g, dict) else None})
        
        # Shared memories
        for m in self.long_term.get("shared_memories", []):
            if isinstance(m, dict) and kw in m.get("memory", "").lower():
                results.append({"type": "shared_memory",
                                "content": m.get("memory"), "data": m})
        
        return results[:limit]
    
    # -- SUMMARY FOR LLM --------------------------------------
    def get_summary(self, max_items: int = 15) -> str:
        """
        Build a concise summary for LLM system prompt.
        Only includes high-confidence / important items.
        """
        lines = []
        
        # Top facts (confidence >= 2)
        facts = self.get_facts(min_confidence=2)[:5]
        if facts:
            fact_lines = [f"- {f['fact']}" for f in facts]
            lines.append("Sir's traits:\n" + "\n".join(fact_lines))
        
        # Important people
        people = self.get_important_people(min_importance=7)[:5]
        if people:
            people_lines = [
                f"- {p['name']} ({p.get('relation', 'known')}, importance {p.get('importance')}/10)"
                for p in people
            ]
            lines.append("People in Sir's life:\n" + "\n".join(people_lines))
        
        # Active goals
        active = self.get_goals("active")[:3]
        if active:
            goal_lines = []
            for g in active:
                text = g.get("goal", "") if isinstance(g, dict) else g
                goal_lines.append(f"- {text}")
            lines.append("Active goals:\n" + "\n".join(goal_lines))
        
        # Loved things
        loved = self.long_term.get("loved_things", [])[:3]
        if loved:
            loved_names = []
            for l in loved:
                if isinstance(l, dict):
                    loved_names.append(l.get("thing", ""))
            if loved_names:
                lines.append("Sir loves: " + ", ".join(loved_names))
        
        # Relationship level
        level = self.personality.get("relationship_level", "new_friend")
        hours = self.personality.get("time_spent_hours", 0)
        lines.append(f"Time together: {hours}h (relationship: {level})")
        
        return "\n\n".join(lines)
    
    def get_companion_context(self) -> str:
        """
        Rich context for Companion Mode - includes shared memories.
        Only called when mode_manager.is_companion() is True.
        """
        if not mode_manager.is_companion():
            return ""
        
        lines = [self.get_summary()]
        
        # Add shared memories
        shared = self.get_shared_memories(limit=5)
        if shared:
            mem_lines = [f"- {m.get('memory')}" for m in shared]
            lines.append("Shared moments with Sir:\n" + "\n".join(mem_lines))
        
        return "\n\n".join(lines)

# -- Singleton ------------------------------------------------
memory = MemoryManager()

# -- Quick helper functions (for convenience) ----------------
def save_fact(fact: str, **kw):      return memory.save_fact(fact, **kw)
def save_person(name: str, **kw):    return memory.save_person(name, **kw)
def save_goal(goal: str, **kw):      return memory.save_goal(goal, **kw)
def get_summary():                    return memory.get_summary()
def recall(kw: str):                  return memory.recall(kw)

# -- Test block -----------------------------------------------
if __name__ == "__main__":
    print("\n--- Memory Test ---\n")
    
    # Save facts
    memory.save_fact("Sir is building an AGI project", category="goal", confidence=5)
    memory.save_fact("Sir plays FreeFire", category="hobby", confidence=3)
    memory.save_fact("Sir codes in Python", category="skill", confidence=8)
    
    # Save people
    memory.save_person("Vishakha", relation="special", importance=10,
                       notes="Someone very special to Sir")
    memory.save_person("Naveen", relation="best_friend", importance=9,
                       notes="Best friend since school")
    memory.save_person("Random Guy", relation="acquaintance", importance=3)
    
    # Save goals
    memory.save_goal("Build the world's first AGI", status="active")
    memory.save_goal("Launch YouTube channel", status="active")
    memory.save_goal("Complete Jarvis V2", status="active")
    
    # Save liked
    memory.save_liked("Can We Kiss Forever", confidence=3)
    memory.save_liked("Vardan YouTube channel", confidence=2)
    memory.save_disliked("waiting in queues", confidence=1)
    
    # Save shared memory
    memory.save_shared_memory("Sir coded me at 2 AM fixing the TTS bug", importance=8)
    memory.save_shared_memory("First time I got sarcastic and Sir laughed", importance=7)
    
    # Time tracking
    memory.add_time_spent(60)  # 1 hour
    memory.upgrade_relationship()
    
    # Recall
    print("-- Recall 'vishakha' --")
    for r in memory.recall("vishakha"):
        print(f"  [{r['type']:10}] {r['content']}")
    
    print("\n-- Recall 'code' --")
    for r in memory.recall("code"):
        print(f"  [{r['type']:10}] {r['content']}")
    
    # Important people
    print("\n-- Top people (importance >= 7) --")
    for p in memory.get_important_people(7):
        print(f"  {p['name']:15} ({p['relation']}) importance: {p['importance']}")
    
    # Active goals
    print("\n-- Active goals --")
    for g in memory.get_goals("active"):
        text = g.get("goal") if isinstance(g, dict) else g
        print(f"  - {text}")
    
    # LLM Summary
    print("\n-- LLM Summary --")
    print(memory.get_summary())
    
    print("\n[OK] Memory test complete\n")