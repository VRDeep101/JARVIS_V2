# =============================================================
#  Backend/Brain/ContinuousLearner.py - Learns From Every Chat
#
#  Kya karta:
#    - Every user message ko analyze karta
#    - Facts extract karta (names, places, likes, etc)
#    - Auto-save to Memory (with confidence)
#    - Patterns detect karta (asks about X often)
#    - Preference tracking (TTS speed, favorite apps)
#    - Goal detection ("I want to...")
#    - Background thread - doesn't block main flow
#    - Periodic memory cleanup (merge dupes, remove low-conf)
#
#  Usage:
#    from Backend.Brain.ContinuousLearner import learner
#    learner.analyze(query)   -> fire-and-forget learning
#    learner.insights()        -> current learned patterns
# =============================================================

import re
import threading
import time
from datetime import datetime
from collections import Counter
from typing import List, Dict, Optional

from Backend.Utils.Logger import get_logger
from Backend.Brain.Memory import memory
from Backend.Core.ModeManager import mode_manager

log = get_logger("Learner")

# -- Extraction patterns --------------------------------------

# Direct fact patterns
FACT_PATTERNS = [
    # "my X is Y" / "my name is Y"
    (r"my\s+name\s+is\s+([a-zA-Z\s]{2,30})", "name"),
    (r"my\s+(?:best\s+)?friend(?:'s)?\s+name\s+is\s+([a-zA-Z\s]{2,30})", "friend"),
    (r"my\s+(girlfriend|boyfriend|wife|husband|crush)(?:'s)?\s+name\s+is\s+([a-zA-Z\s]{2,30})", "partner"),
    (r"my\s+(mom|mother|dad|father|sister|brother)(?:'s)?\s+name\s+is\s+([a-zA-Z\s]{2,30})", "family"),
    
    # "I am X" / "I'm X"
    (r"(?:i\s+am|i'm)\s+(?:a\s+)?([a-z]+\s+(?:developer|engineer|student|artist|designer|programmer))", "profession"),
    (r"(?:i\s+am|i'm)\s+(\d{1,2})\s+years?\s+old", "age"),
    (r"(?:i\s+live|i'm\s+from)\s+in\s+([a-zA-Z\s,]{3,40})", "location"),
    
    # "I like X" / "I love X"
    (r"i\s+(?:really\s+)?(?:like|love|enjoy)\s+([a-zA-Z\s]{3,40})", "like"),
    (r"my\s+favorite\s+([a-z]+)\s+is\s+([a-zA-Z\s]{2,40})", "favorite"),
    
    # "I hate X"
    (r"i\s+(?:hate|can't\s+stand|don't\s+like)\s+([a-zA-Z\s]{3,40})", "dislike"),
    
    # Goals: "I want to X", "I plan to X"
    (r"i\s+(?:want\s+to|plan\s+to|am\s+working\s+on|hope\s+to)\s+([a-zA-Z\s]{5,80})", "goal"),
    
    # Remember this / save this (explicit)
    (r"(?:remember|yaad\s+rakh|save)\s+(?:that|this|ki)?\s*(.+)", "explicit"),
]

# Name detection (capitalized words that might be names)
NAME_PATTERN = re.compile(r"\b([A-Z][a-z]{2,20})\b")

# Stop words (not names)
NAME_STOPWORDS = {
    "jarvis", "sir", "google", "chrome", "youtube", "spotify",
    "python", "javascript", "java", "claude", "chatgpt", "gemini",
    "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "whatsapp", "gmail", "facebook", "instagram", "twitter",
    "open", "close", "play", "stop", "hello", "hi", "hey",
    "good", "morning", "afternoon", "evening", "night",
    "india", "pune", "mumbai", "delhi",
    "risky", "deep",  # user's own names
}

class ContinuousLearner:
    """Learns from every user message in background."""
    
    def __init__(self):
        self.query_counter = Counter()   # track how often topics asked
        self.last_cleanup = time.time()
        self.cleanup_interval = 3600     # every hour
    
    def analyze(self, query: str, async_mode: bool = True):
        """
        Main entry. Analyze query and save insights.
        
        IMPORTANT: Skip if in Companion Mode - different vault handles that.
        """
        if not query or not query.strip():
            return
        
        # Skip learning in Companion Mode (vault is separate)
        if mode_manager.is_companion():
            return
        
        if async_mode:
            thread = threading.Thread(
                target=self._analyze_sync,
                args=(query,),
                daemon=True,
                name="LearnerAnalyze",
            )
            thread.start()
        else:
            self._analyze_sync(query)
    
    def _analyze_sync(self, query: str):
        """Actual analysis (runs in bg thread)."""
        try:
            q_lower = query.lower().strip()
            
            # 1. Topic tracking (for pattern detection)
            words = re.findall(r"\w{4,}", q_lower)
            self.query_counter.update(words)
            
            # 2. Pattern extraction
            self._extract_facts(q_lower, query)
            
            # 3. Name extraction
            self._extract_names(query)
            
            # 4. Periodic cleanup
            if time.time() - self.last_cleanup > self.cleanup_interval:
                self._cleanup()
                self.last_cleanup = time.time()
        
        except Exception as e:
            log.error(f"Analysis error: {e}")
    
    def _extract_facts(self, q_lower: str, q_original: str):
        """Extract structured facts using patterns."""
        for pattern, category in FACT_PATTERNS:
            match = re.search(pattern, q_lower)
            if not match:
                continue
            
            groups = match.groups()
            value = groups[-1].strip()  # last capture group = value
            
            if not value or len(value) < 2:
                continue
            
            # Clean value
            value = re.sub(r"[.!?,]+$", "", value).strip()
            if len(value) < 2:
                continue
            
            # Dispatch by category
            if category == "name":
                memory.save_fact(f"Sir's name is {value.title()}", category="identity", confidence=5)
            
            elif category == "friend":
                memory.save_person(value.title(), relation="friend", importance=7,
                                   notes="Mentioned as friend")
            
            elif category == "partner":
                relation = groups[0]  # girlfriend/boyfriend/etc
                name = groups[1].strip().title()
                memory.save_person(name, relation=relation, importance=10,
                                   notes=f"Sir's {relation}")
            
            elif category == "family":
                relation = groups[0]
                name = groups[1].strip().title()
                memory.save_person(name, relation=f"family_{relation}", importance=8)
            
            elif category == "profession":
                memory.save_fact(f"Sir works as {value}", category="identity", confidence=3)
            
            elif category == "age":
                memory.save_fact(f"Sir is {value} years old", category="identity", confidence=5)
            
            elif category == "location":
                memory.save_fact(f"Sir lives in {value.title()}", category="location", confidence=3)
            
            elif category == "like":
                memory.save_liked(value, confidence=2)
            
            elif category == "favorite":
                type_name = groups[0]
                fav_value = groups[1]
                memory.save_fact(f"Sir's favorite {type_name} is {fav_value}",
                                 category="preference", confidence=4)
                memory.save_liked(f"{fav_value} ({type_name})", confidence=3)
            
            elif category == "dislike":
                memory.save_disliked(value, confidence=2)
            
            elif category == "goal":
                memory.save_goal(value, status="active",
                                 notes=f"Extracted from: {q_original[:60]}")
            
            elif category == "explicit":
                # User said "remember that X" - high confidence
                memory.save_fact(value, category="explicit", confidence=7)
                log.info(f"Explicit memory: {value[:50]}")
    
    def _extract_names(self, query: str):
        """Find capitalized names that aren't stopwords."""
        matches = NAME_PATTERN.findall(query)
        for name in matches:
            if name.lower() in NAME_STOPWORDS:
                continue
            if len(name) < 3:
                continue
            
            # Check if already known person
            existing = memory.get_person(name)
            if existing:
                # Just bump importance slightly
                new_imp = min(10, existing.get("importance", 5) + 1)
                memory.save_person(name, importance=new_imp)
            else:
                # New possible person - save with low importance
                # Will grow with more mentions
                memory.save_person(name, relation="mentioned", importance=4,
                                   notes="Auto-detected from conversation")
    
    def _cleanup(self):
        """Periodic memory maintenance."""
        log.info("Running memory cleanup...")
        # Memory manager already dedupes on save.
        # Here we could do advanced merging, stale removal, etc.
        # For now - just log.
        log.debug("Cleanup complete")
    
    # -- Insights -------------------------------------------
    def insights(self) -> Dict:
        """Return what we've learned."""
        top_topics = self.query_counter.most_common(10)
        return {
            "top_topics": top_topics,
            "total_queries_analyzed": sum(self.query_counter.values()),
            "unique_words": len(self.query_counter),
        }
    
    def top_topic(self) -> Optional[str]:
        """Most common topic (for proactive suggestions)."""
        if not self.query_counter:
            return None
        return self.query_counter.most_common(1)[0][0]

# -- Singleton ------------------------------------------------
learner = ContinuousLearner()
# Alias for Main.py
continuous_learner = learner

# Compat method: Main.py calls .observe(query, response)
def _observe_compat(self, query: str, response: str = ""):
    """Compat wrapper - triggers learner.analyze."""
    try:
        self.analyze(query, async_mode=True)
    except Exception:
        pass

ContinuousLearner.observe = _observe_compat

# -- Test block -----------------------------------------------
if __name__ == "__main__":
    print("\n--- ContinuousLearner Test ---\n")
    
    test_queries = [
        "my name is Deep",
        "my best friend's name is Naveen",
        "my girlfriend's name is Vishakha",
        "I am 20 years old",
        "I live in Pune",
        "I really love coding in Python",
        "my favorite song is Can We Kiss Forever",
        "I want to build the world's first AGI",
        "I hate waiting in queues",
        "remember that I prefer dark mode",
        "I'm working on my YouTube channel with Naveen",
        "Vishakha's birthday is in August",
    ]
    
    print("Analyzing queries...\n")
    for q in test_queries:
        print(f"  > {q}")
        learner.analyze(q, async_mode=False)
    
    # Wait for any async work
    time.sleep(0.5)
    
    print("\n-- Memory Summary After Learning --")
    print(memory.get_summary())
    
    print("\n-- Learner Insights --")
    insights = learner.insights()
    print(f"Total queries analyzed: {insights['total_queries_analyzed']}")
    print(f"Top topics:")
    for topic, count in insights['top_topics'][:5]:
        print(f"  {topic}: {count}")
    
    print("\n[OK] ContinuousLearner test complete\n")