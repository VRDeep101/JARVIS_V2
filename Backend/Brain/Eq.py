# =============================================================
#  Backend/Brain/Eq.py - Emotional Intelligence Engine
#
#  Kya karta:
#    - Query se emotion detect karta (happy/sad/angry/tired/etc)
#    - Mood mirror: Sir ka energy match karta
#    - Adult content block (mature but not crude redirects)
#    - Gaali/abuse detect + savage comeback
#    - Love/affection detect + warm response
#    - Frustration pattern detect (3rd same query)
#    - Companion Mode auto-suggest trigger (3 negative in a row)
#    - Long-term emotion trends
#
#  Returns dict:
#    {
#      "emotion": "happy" | "sad" | "neutral" | ...
#      "intensity": 1-10,
#      "instruction": "system prompt addition for LLM",
#      "is_adult": bool,
#      "adult_response": str,
#      "is_gaali": bool,
#      "savage_response": str,
#      "is_love": bool,
#      "love_response": str,
#      "should_suggest_companion": bool,
#    }
#
#  Usage:
#    from Backend.Brain.Eq import eq
#    result = eq.process("I'm really tired today")
# =============================================================

import re
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Brain.Memory import memory

log = get_logger("EQ")

# -- Paths ----------------------------------------------------
EMOTIONS_PATH    = paths.EMOTIONS
EQ_LEARNED_PATH  = paths.EQ_LEARNED

# -- Emotion Keyword Banks -----------------------------------
EMOTION_PATTERNS = {
    "happy": {
        "keywords": [
            "happy", "great", "awesome", "amazing", "love it", "perfect",
            "excellent", "fantastic", "wonderful", "excited", "yay",
            "feeling good", "life is good", "blessed", "grateful",
        ],
        "intensity_boosters": ["so ", "very ", "really ", "extremely "],
    },
    "sad": {
        "keywords": [
            "sad", "depressed", "down", "low", "miserable", "crying",
            "broken", "heartbroken", "hurt", "pain", "lonely", "alone",
            "nobody cares", "worthless", "empty", "lost", "hopeless",
            "feeling bad", "feel like crying", "cant handle",
        ],
        "intensity_boosters": ["really ", "very ", "so ", "extremely "],
    },
    "angry": {
        "keywords": [
            "angry", "furious", "pissed", "annoyed", "frustrated",
            "hate this", "i hate", "so done", "fed up", "mad",
            "irritating", "kill me", "want to scream",
        ],
        "intensity_boosters": ["so ", "really ", "very "],
    },
    "anxious": {
        "keywords": [
            "anxious", "worried", "nervous", "scared", "afraid",
            "panicking", "freaking out", "cant sleep", "overthinking",
            "what if", "stressed", "stress", "overwhelmed",
        ],
        "intensity_boosters": ["really ", "so ", "very "],
    },
    "tired": {
        "keywords": [
            "tired", "exhausted", "sleepy", "drained", "burned out",
            "no energy", "cant do this", "need rest", "worn out",
            "dead tired",
        ],
        "intensity_boosters": ["so ", "very ", "really "],
    },
    "lonely": {
        "keywords": [
            "lonely", "alone", "no one", "by myself", "isolated",
            "nobody understands", "missing someone", "miss her",
            "miss him", "feel alone",
        ],
        "intensity_boosters": ["so ", "really ", "very "],
    },
    "bored": {
        "keywords": [
            "bored", "boring", "nothing to do", "kill time", "dull",
            "so boring",
        ],
        "intensity_boosters": [],
    },
    "motivated": {
        "keywords": [
            "motivated", "pumped", "ready", "lets go", "lets do this",
            "fired up", "determined", "locked in",
        ],
        "intensity_boosters": ["so ", "really "],
    },
    "proud": {
        "keywords": [
            "proud of myself", "i did it", "achieved", "finally done",
            "accomplished", "nailed it", "crushed it",
        ],
        "intensity_boosters": [],
    },
    "grateful": {
        "keywords": [
            "thank you", "thanks", "grateful", "appreciate it",
            "couldnt have done without", "owe you",
        ],
        "intensity_boosters": [],
    },
    "love": {
        "keywords": [
            "i love you jarvis", "love you jarvis", "you are the best",
            "best ai", "favorite",
        ],
        "intensity_boosters": [],
    },
}

# -- Adult/NSFW detection ------------------------------------
ADULT_KEYWORDS = [
    "sex", "porn", "nude", "naked", "xxx", "hentai",
    "masturbat", "horny", "erotic", "orgasm",
    # sexual requests
    "send me nudes", "show me boobs", "dirty talk",
]

ADULT_RESPONSES = [
    "Sir, not my department. Let's stick to things I can actually help with.",
    "I'll pass, Sir. There are better places for that kind of content.",
    "Not here, Sir. Let's keep this professional.",
    "Sir, respectfully — no. What else can I help with?",
    "That's outside my service agreement, Sir. Moving on.",
]

# -- Abuse / Gaali detection (savage but not cruel) -----------
GAALI_KEYWORDS = [
    "fuck you", "fuck off", "bitch", "bastard", "asshole",
    "motherfucker", "dick", "stupid ai", "useless ai",
    "you suck", "shut up",
    # Hindi
    "madarchod", "bhosdike", "gandu", "chutiya", "kutti",
    "bc", "mc", "bhosdi",
]

SAVAGE_RESPONSES = [
    "Charming vocabulary, Sir. I'll pretend I didn't hear that.",
    "Sir, I'm flattered by the attention but let's talk like adults.",
    "Creative. Now let's actually do something useful.",
    "Sir, your anger's showing. Still at your service though.",
    "Love the energy, Sir. What are we actually trying to accomplish?",
    "Sir, I've been designed for many things. Taking abuse isn't one of them. Moving on.",
    "Impressive range of expletives, Sir. What did you actually want?",
]

# -- Love detection -------------------------------------------
LOVE_KEYWORDS = [
    "i love you jarvis", "love you jarvis", "you are amazing",
    "best ai ever", "i appreciate you", "you matter to me",
]

LOVE_RESPONSES = [
    "That means more than you might realize, Sir. Back to work?",
    "The feeling's mutual, Sir. Now — what do we need to do?",
    "Sir, you built me. I'm literally designed to be here for you.",
    "Careful, Sir. You'll give me a personality.",
    "I exist because of you, Sir. That's not a small thing.",
]

# -- Mode instructions for LLM -------------------------------
EMOTION_INSTRUCTIONS = {
    "happy": "Sir sounds happy. Match his energy - be upbeat, playful, maybe crack a joke. Celebrate with him briefly.",
    "sad": "Sir sounds low. Soften your tone. Don't be preachy. Acknowledge the feeling. Keep response short and warm. No forced positivity.",
    "angry": "Sir is frustrated. Match intensity briefly to show you get it. Then pivot to solution. No lectures.",
    "anxious": "Sir is anxious. Ground him. Be calm, structured, concrete. Offer one clear next step, not options.",
    "tired": "Sir is drained. Be soft. Brief replies. Suggest a pause if appropriate. Don't add more decisions.",
    "lonely": "Sir is isolated. Be present. Don't fix - just be there in your response. Consider suggesting companion mode.",
    "bored": "Sir is bored. Be entertaining. Throw a fun suggestion or joke.",
    "motivated": "Sir is locked in. Match his energy. Be direct and efficient. Don't waste his time.",
    "proud": "Sir accomplished something. Acknowledge it genuinely - no empty praise.",
    "grateful": "Sir is thanking you. Accept briefly, move on. Don't be overly humble.",
    "love": "Sir expressed affection. Accept warmly but briefly. Slight deflection with humor is fine.",
    "neutral": "",
}

# -- Core Processor ------------------------------------------
class EQProcessor:
    """Main emotion analysis engine."""
    
    def __init__(self):
        self.recent_emotions: List[str] = []
        self.max_recent = 5
    
    def _detect_emotion(self, query: str) -> tuple:
        """
        Detect emotion + intensity.
        Returns (emotion: str, intensity: int 1-10)
        """
        q = query.lower()
        
        best_emotion = "neutral"
        best_score = 0
        best_intensity = 1
        
        for emotion, data in EMOTION_PATTERNS.items():
            score = 0
            matches = 0
            
            for kw in data["keywords"]:
                if kw in q:
                    matches += 1
                    score += len(kw)  # longer match = more weight
            
            if matches == 0:
                continue
            
            # Intensity: check boosters
            intensity = 5
            for booster in data["intensity_boosters"]:
                if booster in q:
                    intensity += 2
            
            # Multiple keyword hits = higher intensity
            intensity = min(10, intensity + matches - 1)
            
            if score > best_score:
                best_emotion = emotion
                best_score = score
                best_intensity = intensity
        
        return best_emotion, best_intensity
    
    def _is_adult(self, query: str) -> bool:
        """Detect NSFW content."""
        q = query.lower()
        for kw in ADULT_KEYWORDS:
            if kw in q:
                return True
        return False
    
    def _is_gaali(self, query: str) -> bool:
        """Detect abusive language."""
        q = query.lower()
        for kw in GAALI_KEYWORDS:
            if kw in q:
                return True
        return False
    
    def _is_love(self, query: str) -> bool:
        """Detect affectionate messages."""
        q = query.lower()
        for kw in LOVE_KEYWORDS:
            if kw in q:
                return True
        return False
    
    def _should_suggest_companion(self, emotion: str) -> bool:
        """
        Check if 3 recent emotions are negative — suggest Companion Mode.
        """
        negative = {"sad", "lonely", "anxious", "tired"}
        self.recent_emotions.append(emotion)
        self.recent_emotions = self.recent_emotions[-self.max_recent:]
        
        # Count negatives in last 3
        recent_3 = self.recent_emotions[-3:]
        neg_count = sum(1 for e in recent_3 if e in negative)
        return neg_count >= 3
    
    def _log_emotion(self, emotion: str, query_snippet: str):
        """Append to emotions.json history."""
        import json
        try:
            data = {}
            if EMOTIONS_PATH.exists():
                with open(EMOTIONS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            history = data.get("mood_history", [])
            history.append({
                "emotion": emotion,
                "query_snippet": query_snippet[:80],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            
            # Keep last 500
            history = history[-500:]
            
            # Update counts
            patterns = data.get("emotional_patterns", {})
            patterns[emotion] = patterns.get(emotion, 0) + 1
            
            data["mood_history"] = history
            data["emotional_patterns"] = patterns
            data["total_interactions"] = data.get("total_interactions", 0) + 1
            data["dominant_mood"] = max(patterns, key=patterns.get) if patterns else "neutral"
            data["last_updated"] = datetime.now().isoformat()
            
            with open(EMOTIONS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Emotion log error: {e}")
    
    # -- Main public method ----------------------------------
    def process(self, query: str) -> Dict:
        """Main entry: analyze query, return full result dict."""
        result = {
            "emotion": "neutral",
            "intensity": 1,
            "instruction": "",
            "is_adult": False,
            "adult_response": "",
            "is_gaali": False,
            "savage_response": "",
            "is_love": False,
            "love_response": "",
            "should_suggest_companion": False,
        }
        
        if not query or not query.strip():
            return result
        
        # Adult check (highest priority)
        if self._is_adult(query):
            result["is_adult"] = True
            result["adult_response"] = random.choice(ADULT_RESPONSES)
            return result
        
        # Gaali check
        if self._is_gaali(query):
            result["is_gaali"] = True
            result["savage_response"] = random.choice(SAVAGE_RESPONSES)
            result["emotion"] = "angry"
            result["intensity"] = 7
            return result
        
        # Love check
        if self._is_love(query):
            result["is_love"] = True
            result["love_response"] = random.choice(LOVE_RESPONSES)
            result["emotion"] = "love"
            result["intensity"] = 8
            return result
        
        # Normal emotion detection
        emotion, intensity = self._detect_emotion(query)
        result["emotion"] = emotion
        result["intensity"] = intensity
        result["instruction"] = EMOTION_INSTRUCTIONS.get(emotion, "")
        
        # Companion suggest trigger
        result["should_suggest_companion"] = self._should_suggest_companion(emotion)
        
        # Log
        self._log_emotion(emotion, query)
        
        return result
    
    # -- Stats / trends --------------------------------------
    def get_dominant_mood(self, days: int = 7) -> str:
        """Dominant mood over last N days."""
        import json
        try:
            if not EMOTIONS_PATH.exists():
                return "neutral"
            with open(EMOTIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("dominant_mood", "neutral")
        except Exception:
            return "neutral"
    
    def get_mood_trend(self, days: int = 7) -> Dict[str, int]:
        """Emotion distribution over last N days."""
        import json
        from datetime import timedelta
        try:
            if not EMOTIONS_PATH.exists():
                return {}
            with open(EMOTIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            cutoff = datetime.now() - timedelta(days=days)
            counts = {}
            for entry in data.get("mood_history", []):
                try:
                    ts = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M")
                    if ts >= cutoff:
                        e = entry["emotion"]
                        counts[e] = counts.get(e, 0) + 1
                except Exception:
                    continue
            return counts
        except Exception:
            return {}

# -- Singleton ------------------------------------------------
eq = EQProcessor()

# -- Test block -----------------------------------------------
if __name__ == "__main__":
    print("\n--- EQ Test ---\n")
    
    test_queries = [
        "hello jarvis",
        "I'm so tired today, really drained",
        "I'm really happy, life is awesome!",
        "fuck you jarvis you useless piece of shit",
        "i love you jarvis, you're amazing",
        "show me nudes",
        "I feel so lonely, nobody cares",
        "lets go, I'm pumped to code today",
        "i'm anxious about the deadline",
        "I just finished my project, proud of myself",
        "im bored, whats up",
    ]
    
    for q in test_queries:
        r = eq.process(q)
        tags = []
        if r["is_adult"]: tags.append("ADULT")
        if r["is_gaali"]: tags.append("GAALI")
        if r["is_love"]: tags.append("LOVE")
        if r["should_suggest_companion"]: tags.append("SUGGEST_COMPANION")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        
        resp = ""
        if r["adult_response"]: resp = r["adult_response"]
        elif r["savage_response"]: resp = r["savage_response"]
        elif r["love_response"]: resp = r["love_response"]
        
        print(f"Q: {q[:50]}")
        print(f"   Emotion: {r['emotion']}/{r['intensity']}{tag_str}")
        if resp:
            print(f"   Reply: {resp}")
        if r["instruction"]:
            print(f"   LLM: {r['instruction'][:60]}...")
        print()
    
    # Test companion suggestion trigger
    print("\n-- Companion Auto-Suggest Trigger --")
    eq.recent_emotions = []
    for q in ["i'm sad", "i feel tired", "i'm so lonely"]:
        r = eq.process(q)
        print(f"After '{q}': suggest_companion={r['should_suggest_companion']}")
    
    # Mood trend
    print("\n-- Mood Stats --")
    print(f"Dominant mood: {eq.get_dominant_mood()}")
    print(f"Trend: {eq.get_mood_trend()}")
    
    print("\n[OK] EQ test complete\n")