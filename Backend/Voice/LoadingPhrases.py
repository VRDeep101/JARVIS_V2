# =============================================================
#  Backend/Voice/LoadingPhrases.py - Filler Lines
#
#  Kya karta:
#    - 60+ loading phrases for background tasks
#    - Mood-aware selection (serious task vs casual)
#    - Category-specific (image gen vs search vs file op)
#    - No repetition in short timespan
#    - Long-task follow-ups ("still working, Sir")
#
#  Usage:
#    from Backend.Voice.LoadingPhrases import phrases
#    phrases.get("default")       -> "Give me a moment, Sir"
#    phrases.get("image")         -> "Painting that for you..."
#    phrases.get_long_task()      -> "Still working, Sir. Any other task?"
#    phrases.post_task()          -> "Anything else, Sir?"
# =============================================================

import random
from collections import deque
from typing import Optional, Dict, List

from Backend.Utils.Logger import get_logger

log = get_logger("LoadingPhrases")

# =============================================================
#  PHRASE LIBRARY (60+ lines, categorized)
# =============================================================

PHRASES: Dict[str, List[str]] = {
    # ── General (used when category unknown) ──
    "default": [
        "Give me a moment, Sir.",
        "One second, Sir.",
        "Hold on, Sir.",
        "Working on it.",
        "On it, Sir.",
        "Processing that now.",
        "Getting on it.",
        "Just a moment.",
        "Right away, Sir.",
        "Stand by.",
        "Let me handle this.",
        "Moment please, Sir.",
        "Almost there.",
        "Executing now.",
        "Coming up, Sir.",
    ],
    
    # ── Image generation ──
    "image": [
        "Painting that for you, Sir.",
        "Generating your image now.",
        "Working on the image, Sir.",
        "Creating visuals, one moment.",
        "Image generation in progress.",
        "Drawing that up, Sir.",
        "Rendering now.",
        "Preparing your image, Sir.",
    ],
    
    # ── Web search / realtime ──
    "search": [
        "Searching the web, Sir.",
        "Fetching the latest, Sir.",
        "Looking that up for you.",
        "Scanning sources now.",
        "Pulling fresh data, Sir.",
        "Checking what's out there.",
        "On it, pulling results.",
        "Searching now, Sir.",
    ],
    
    # ── AI web automation (Claude/GPT/Gemini) ──
    "ai_web": [
        "Opening the AI for the best output, Sir. Please wait.",
        "Routing to Claude for top-quality results. One moment.",
        "Firing up the AI service. Hold tight, Sir.",
        "Switching to the right AI for this, Sir.",
        "Connecting to the AI, Sir. Moment please.",
    ],
    
    # ── App opening ──
    "opening_app": [
        "Opening now, Sir.",
        "Launching for you.",
        "Starting it up, Sir.",
        "Bringing that up, Sir.",
        "On it, opening now.",
    ],
    
    # ── File / system ops ──
    "file_op": [
        "Handling the file, Sir.",
        "Working with that now.",
        "Processing the file.",
        "On the file, Sir.",
    ],
    
    # ── Long task in progress (>10s) ──
    "long_task": [
        "Still working on it, Sir. Any other task?",
        "This is taking a while, Sir. I can multitask if you need something.",
        "That task is in progress, Sir. Anything else I can do?",
        "Still on it, Sir. Feel free to throw something else at me.",
        "Background task still running, Sir. What else do you need?",
        "Working away on it, Sir. Another command?",
    ],
    
    # ── Background task done ──
    "task_complete": [
        "Done, Sir. Displaying the result.",
        "Task complete, Sir. Here you go.",
        "That's ready, Sir. Shall I show it?",
        "Finished, Sir. Want to see it?",
        "All done. Ready to display.",
        "Task complete. Here it is, Sir.",
    ],
    
    # ── Task failed mid-way ──
    "task_failed": [
        "Sir, that task didn't complete. Restart it?",
        "The task errored out, Sir. Try again?",
        "Something broke mid-way, Sir. Want to retry?",
        "Task failed, Sir. Shall I attempt it again?",
    ],
    
    # ── Post-task prompts ──
    "post_task": [
        "Anything else, Sir?",
        "What's next, Sir?",
        "Done. Need anything more?",
        "All set. What else?",
        "Task done. What now, Sir?",
        "Anything more I can do?",
        "Ready for the next one, Sir.",
    ],
    
    # ── Security mode specific ──
    "security": [
        "Scanning for threats, Sir. Moment please.",
        "Running security check now.",
        "Analyzing for risks, Sir.",
        "Security scan in progress.",
    ],
    
    # ── Scanning mode specific ──
    "scanning": [
        "Scanning now, Sir.",
        "Running the scan, Sir.",
        "Gathering data, Sir.",
        "Sweeping the area, Sir.",
    ],
    
    # ── Memory / data extraction ──
    "analyzing": [
        "Analyzing that, Sir.",
        "Reading through it, Sir.",
        "Processing the information.",
        "Working through it now.",
    ],
}

# =============================================================
#  PhraseManager class
# =============================================================

class PhraseManager:
    """Random phrase picker with no-repeat memory."""
    
    def __init__(self, history_size: int = 8):
        # Track last N phrases to avoid repetition
        self.recent = deque(maxlen=history_size)
    
    def get(self, category: str = "default") -> str:
        """Get a phrase from the category, avoiding recent repeats."""
        pool = PHRASES.get(category)
        if not pool:
            pool = PHRASES["default"]
        
        # Filter out recent phrases
        fresh = [p for p in pool if p not in self.recent]
        
        # If all used recently, reset
        if not fresh:
            fresh = pool
        
        choice = random.choice(fresh)
        self.recent.append(choice)
        return choice
    
    def get_long_task(self) -> str:
        """Follow-up for tasks running > 10 seconds."""
        return self.get("long_task")
    
    def post_task(self) -> str:
        """Message after completing a task."""
        return self.get("post_task")
    
    def task_complete(self) -> str:
        """Message when background task finishes."""
        return self.get("task_complete")
    
    def task_failed(self) -> str:
        """Message when background task fails."""
        return self.get("task_failed")
    
    def categories(self) -> List[str]:
        """All available phrase categories."""
        return list(PHRASES.keys())
    
    def count(self, category: str = None) -> int:
        """Count phrases in category (or total)."""
        if category:
            return len(PHRASES.get(category, []))
        return sum(len(v) for v in PHRASES.values())

# =============================================================
#  Singleton
# =============================================================
phrases = PhraseManager()
# Alias (Main.py uses this name)

# =============================================================
# =============================================================
#  Singleton
# =============================================================
phrases = PhraseManager()

# Alias (Main.py uses this name)
loading_phrases = phrases

# =============================================================
#  TEST BLOCK
# =============================================================
#  TEST BLOCK

# =============================================================
if __name__ == "__main__":
    print("\n--- LoadingPhrases Test ---\n")
    
    print(f"Total phrase categories: {len(phrases.categories())}")
    print(f"Total phrases: {phrases.count()}\n")
    
    for cat in phrases.categories():
        print(f"  {cat:15} -> {phrases.count(cat)} phrases")
    
    print("\n-- Sample from each category --\n")
    for cat in phrases.categories():
        print(f"  [{cat:15}] {phrases.get(cat)}")
    
    print("\n-- No-repeat test (default) --")
    for i in range(10):
        print(f"  {i+1:2}. {phrases.get('default')}")
    
    print("\n-- Long task flow --")
    print(f"  Long task : {phrases.get_long_task()}")
    print(f"  Complete  : {phrases.task_complete()}")
    print(f"  Failed    : {phrases.task_failed()}")
    print(f"  Post      : {phrases.post_task()}")
    
    print("\n[OK] LoadingPhrases test complete\n")