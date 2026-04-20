# =============================================================
#  Backend/Core/Router.py - Smart Query Router
#
#  Kya karta:
#    - Fast local rule-based routing (instant for obvious commands)
#    - Fallback to Cohere LLM for ambiguous queries
#    - Multiple simultaneous intents support (parallel exec)
#    - Mode-aware (certain commands only in certain modes)
#    - Returns structured intent: action + target + params
#
#  Routes to:
#    GENERAL       - Jarvis own chat (Chatbot.py)
#    REALTIME      - Web search (RealtimeSearchEngine)
#    OPEN / CLOSE  - Apps (AppRegistry)
#    PLAY          - YouTube or Spotify
#    SYSTEM        - Volume/brightness/screenshot/etc
#    GOOGLE_SEARCH - Chrome search
#    YOUTUBE_SEARCH- YouTube search
#    AI_WEB        - Claude/ChatGPT/Gemini on web
#    IMAGE         - Image generation
#    MODE_SWITCH   - Change Jarvis mode
#    WHATSAPP      - Send WhatsApp
#    WEATHER       - Weather query
#    NEWS          - News query
#    WOLFRAM       - Math/science
#    SAVE_DATA     - PersonalData save (notepad)
#    CLEAR_DATA    - Reset command
#    EXIT          - Shut down
#
#  Usage:
#    from Backend.Core.Router import router
#    intents = router.route("open chrome and play shape of you")
#    -> [{"action": "open", "target": "chrome"}, 
#        {"action": "play", "target": "shape of you"}]
# =============================================================

import re
import time
from typing import List, Dict, Optional
from dotenv import dotenv_values

from Backend.Utils.Logger import get_logger
from Backend.Utils.InternetCheck import net
from Backend.Core.ModeManager import mode_manager, Mode
from Backend.Core.ContextManager import context

log = get_logger("Router")

# -- Config ---------------------------------------------------
env = dotenv_values(".env")
COHERE_KEY = env.get("CohereAPIKey", "").strip()

# -- Cohere client (lazy) -------------------------------------
_cohere_client = None

def _get_cohere():
    global _cohere_client
    if _cohere_client is None and COHERE_KEY:
        try:
            import cohere
            _cohere_client = cohere.Client(api_key=COHERE_KEY)
            log.info("Cohere client initialized")
        except Exception as e:
            log.error(f"Cohere init failed: {e}")
    return _cohere_client

# -- Keyword banks --------------------------------------------

# Apps (for OPEN/CLOSE routing)
APP_KEYWORDS = {
    "chrome", "firefox", "edge", "brave", "opera",
    "whatsapp", "telegram", "discord", "slack", "teams",
    "spotify", "youtube music",
    "vscode", "vs code", "visual studio code", "notepad", "notepad++",
    "settings", "calculator", "explorer", "files", "file explorer",
    "instagram", "facebook", "twitter", "x", "linkedin",
    "gmail", "outlook",
    "zoom", "skype",
    "steam", "epic games",
    "photoshop", "figma",
    "obs", "camera",
}

# Code-related (for auto-routing to Claude)
CODE_KEYWORDS = [
    "code", "program", "script", "function", "class", "algorithm",
    "debug", "fix bug", "python", "javascript", "java", "c++", "cpp",
    "html", "css", "sql", "api", "implement", "build app",
    "write code", "code lekh", "code likho", "code banao",
    "website", "app banao", "error fix", "bug fix", "syntax",
]

# Content-related (for auto-routing to ChatGPT)
CONTENT_KEYWORDS = [
    "essay", "article", "blog", "story", "email", "letter",
    "content", "post", "caption", "summary", "paragraph",
    "kuch lekh", "likh do",
]

# AI service names
AI_SERVICES = {
    "claude": ["claude", "claude ai", "claude dot ai"],
    "chatgpt": ["chatgpt", "chat gpt", "gpt", "openai", "chat g p t"],
    "gemini": ["gemini", "bard", "google ai"],
}

# System commands
SYSTEM_KEYWORDS = {
    "screenshot": ["screenshot", "screen shot", "capture screen", "take screenshot"],
    "screen_record_start": ["start recording", "start screen recording", "record screen",
                            "screen record start"],
    "screen_record_stop": ["stop recording", "stop screen recording", "end recording"],
    "volume_up": ["volume up", "increase volume", "louder", "volume badhao",
                  "sound up"],
    "volume_down": ["volume down", "decrease volume", "quieter", "volume kam",
                    "sound down"],
    "mute": ["mute", "silence", "audio mute", "mute karo"],
    "unmute": ["unmute", "audio unmute"],
    "brightness_up": ["brightness up", "increase brightness", "brightness badhao"],
    "brightness_down": ["brightness down", "decrease brightness", "brightness kam"],
    "lock_screen": ["lock screen", "lock pc", "lock computer", "lock kar"],
    "bluetooth_on": ["bluetooth on", "enable bluetooth", "bluetooth chalu"],
    "bluetooth_off": ["bluetooth off", "disable bluetooth", "bluetooth band"],
}

# Realtime triggers (must search web)
REALTIME_KEYWORDS = [
    "today", "current", "latest", "now", "recent", "news",
    "price", "stock", "weather", "temperature",
    "who is", "who won", "score", "live", "update",
    "exchange rate", "kya chal raha", "aaj ka",
]

# Weather keywords
WEATHER_KEYWORDS = ["weather", "temperature", "rain", "forecast",
                    "mausam", "baarish", "hot", "cold"]

# News keywords
NEWS_KEYWORDS = ["news", "headlines", "top stories", "latest news", "khabar"]

# Math/science
WOLFRAM_KEYWORDS = ["calculate", "solve", "integral", "derivative", "equation",
                    "math", "physics problem", "chemistry"]

# -- Router class ---------------------------------------------
class Router:
    """
    Smart router: local rules first (fast), LLM fallback (smart).
    Returns list of intents (can be multiple for 'do X and Y').
    """
    
    def route(self, query: str) -> List[Dict]:
        """
        Main entry: returns list of intent dicts.
        Each dict: {
            "action": str,       # e.g. "open", "play", "general"
            "target": str,       # e.g. "chrome", "shape of you"
            "params": dict,      # extra data
            "confidence": float, # 0-1
        }
        """
        if not query or not query.strip():
            return []
        
        # Resolve pronouns first
        query = context.resolve_pronoun(query.strip())
        q_lower = query.lower()
        
        # -- Priority 0: Mode switching (check first) -------
        target_mode = mode_manager.detect_mode_from_query(q_lower)
        if target_mode:
            return [{
                "action": "mode_switch",
                "target": target_mode.value,
                "params": {},
                "confidence": 1.0,
            }]
        
        # -- Priority 1: Exit command ---------------------
        if q_lower.strip() in ["exit", "quit", "bye jarvis", "stop jarvis",
                                "shutdown jarvis", "turn off jarvis",
                                "goodnight jarvis"]:
            return [{"action": "exit", "target": "", "params": {}, "confidence": 1.0}]
        
        # -- Priority 2: Clear data ------------------------
        clear_triggers = ["clear data", "clear everything", "data uudha de",
                          "data delete kar", "reset jarvis", "wipe data"]
        if any(t in q_lower for t in clear_triggers):
            return [{"action": "clear_data", "target": "", "params": {}, "confidence": 1.0}]
        
        # -- Priority 3: Save personal data -----------------
        save_triggers = ["save personal data", "save personal", "save my data",
                         "personal data save", "open notepad to save"]
        if any(t in q_lower for t in save_triggers):
            return [{"action": "save_data", "target": "", "params": {}, "confidence": 1.0}]
        
        # -- Priority 4: AI web routing ("on ChatGPT/Claude/Gemini") --
        ai_intent = self._check_ai_web(q_lower, query)
        if ai_intent:
            return [ai_intent]
        
        # -- Priority 5: Parse multiple intents ----------------
        # Split on "and" / "then" / commas — handle parallel commands
        intents = self._parse_multi(query)
        
        if intents:
            return intents
        
        # -- Priority 6: Single local rule match ---------
        single = self._classify_single(query)
        if single:
            return [single]
        
        # -- Priority 7: LLM fallback (Cohere) -------------
        llm_intents = self._classify_with_llm(query)
        if llm_intents:
            return llm_intents
        
        # -- Default: general chat -------------------------
        return [{
            "action": "general",
            "target": query,
            "params": {},
            "confidence": 0.5,
        }]
    
    # -- Multi-intent parsing --------------------------------
    def _parse_multi(self, query: str) -> List[Dict]:
        """Handle 'open chrome and play song' -> 2 intents."""
        # Split on ' and ', ' then ', commas
        parts = re.split(r'\s+(?:and|then|phir|after that)\s+|\s*,\s*', query, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) < 2:
            return []
        
        results = []
        for part in parts:
            intent = self._classify_single(part)
            if intent:
                results.append(intent)
        
        # Only return multi if >=2 successfully classified
        return results if len(results) >= 2 else []
    
    # -- Single-intent classification -----------------------
    def _classify_single(self, query: str) -> Optional[Dict]:
        """Classify a single command using local rules."""
        q = query.lower().strip()
        
        # System commands
        for action, triggers in SYSTEM_KEYWORDS.items():
            for t in triggers:
                if t in q:
                    return {"action": "system", "target": action,
                            "params": {}, "confidence": 0.95}
        
        # Image generation
        if any(p in q for p in ["generate image", "create image", "generate images",
                                 "image banao", "picture banao"]):
            # Extract subject
            target = q
            for prefix in ["generate image of", "generate images of", "create image of",
                           "generate image", "create image", "generate images",
                           "image banao", "picture banao"]:
                if prefix in target:
                    target = target.split(prefix, 1)[-1].strip(" -:,")
                    break
            return {"action": "image", "target": target or "art",
                    "params": {}, "confidence": 0.95}
        
        # Play (Spotify vs YouTube)
        play_match = re.match(r'(?:play|chala)\s+(.+)', q)
        if play_match:
            what = play_match.group(1).strip()
            # Check if Spotify mentioned
            if "spotify" in what or "on spotify" in q:
                what = re.sub(r'\s+on\s+spotify\s*$', '', what).strip()
                return {"action": "play", "target": what,
                        "params": {"service": "spotify"}, "confidence": 0.95}
            else:
                return {"action": "play", "target": what,
                        "params": {"service": "youtube"}, "confidence": 0.9}
        
        # Close app
        close_match = re.match(r'(?:close|band\s+kar)\s+(.+)', q)
        if close_match:
            app = close_match.group(1).strip()
            return {"action": "close", "target": app,
                    "params": {}, "confidence": 0.9}
        
        # Open app
        open_match = re.match(r'(?:open|launch|start|chalu\s+kar|khol)\s+(.+)', q)
        if open_match:
            target = open_match.group(1).strip()
            # Check if it's a search context (e.g. "open chrome and search")
            return {"action": "open", "target": target,
                    "params": {}, "confidence": 0.9}
        
        # Google search
        if re.search(r'(?:search|google|dhundho)\s+(.+?)\s+on\s+(?:chrome|google)', q):
            m = re.search(r'(?:search|google|dhundho)\s+(.+?)\s+on\s+(?:chrome|google)', q)
            return {"action": "google_search", "target": m.group(1).strip(),
                    "params": {}, "confidence": 0.95}
        
        if re.match(r'(?:google|search on google)\s+(.+)', q):
            m = re.match(r'(?:google|search on google)\s+(.+)', q)
            return {"action": "google_search", "target": m.group(1).strip(),
                    "params": {}, "confidence": 0.9}
        
        # YouTube search
        if re.search(r'(?:search|find)\s+(.+?)\s+on\s+youtube', q):
            m = re.search(r'(?:search|find)\s+(.+?)\s+on\s+youtube', q)
            return {"action": "youtube_search", "target": m.group(1).strip(),
                    "params": {}, "confidence": 0.95}
        
        # Weather
        if any(k in q for k in WEATHER_KEYWORDS):
            return {"action": "weather", "target": q,
                    "params": {}, "confidence": 0.85}
        
        # News
        if any(k in q for k in NEWS_KEYWORDS):
            return {"action": "news", "target": q,
                    "params": {}, "confidence": 0.85}
        
        # Math / Wolfram
        if any(k in q for k in WOLFRAM_KEYWORDS):
            return {"action": "wolfram", "target": q,
                    "params": {}, "confidence": 0.8}
        
        # WhatsApp
        if "whatsapp" in q or "wa message" in q:
            return {"action": "whatsapp", "target": query,
                    "params": {}, "confidence": 0.85}
        
        # Realtime (web search needed)
        if any(k in q for k in REALTIME_KEYWORDS):
            return {"action": "realtime", "target": query,
                    "params": {}, "confidence": 0.75}
        
        return None
    
    # -- AI web detection -----------------------------------
    def _check_ai_web(self, q_lower: str, original: str) -> Optional[Dict]:
        """
        Detect: "write code X on claude", "search Y on chatgpt",
                "ask gemini about Z"
        """
        for ai_name, aliases in AI_SERVICES.items():
            for alias in aliases:
                # Pattern: "... on {ai}" or "ask {ai} ..."
                on_pattern = rf'\b{re.escape(alias)}\b'
                if re.search(on_pattern, q_lower):
                    # Extract actual query (strip the AI mention)
                    target = original
                    for al in aliases:
                        target = re.sub(rf'\s+on\s+{re.escape(al)}\s*', ' ',
                                        target, flags=re.IGNORECASE)
                        target = re.sub(rf'\bask\s+{re.escape(al)}\s+', '',
                                        target, flags=re.IGNORECASE)
                        target = re.sub(rf'\b{re.escape(al)}\s+pe\s+', '',
                                        target, flags=re.IGNORECASE)
                        target = re.sub(rf'\b{re.escape(al)}\s+',  '',
                                        target, flags=re.IGNORECASE)
                    target = target.strip(" ,.:-")
                    
                    if target:
                        return {
                            "action": "ai_web",
                            "target": target,
                            "params": {"service": ai_name},
                            "confidence": 0.9,
                        }
        return None
    
    # -- LLM fallback ----------------------------------------
    def _classify_with_llm(self, query: str) -> List[Dict]:
        """Last-resort routing using Cohere."""
        if not net.is_online():
            return []
        
        client = _get_cohere()
        if not client:
            return []
        
        preamble = """You are a classifier. Return ONE of these category labels only:
general | realtime | open | close | play | system | image | google_search | youtube_search

Rules:
- general = chat / opinion / knowledge Jarvis can answer directly
- realtime = needs fresh web info (news, prices, current events)
- open/close = app names
- play = music/video
- system = volume/brightness/screenshot
- image = generate image
- google_search = search Google
- youtube_search = search YouTube

Return ONLY the category word, nothing else."""

        try:
            response = client.chat(
                model="command-a-03-2025",
                message=query,
                preamble=preamble,
                temperature=0.1,
            )
            category = response.text.strip().lower().split()[0]
            log.debug(f"LLM routed '{query[:40]}' -> {category}")
            
            return [{
                "action": category,
                "target": query,
                "params": {"from_llm": True},
                "confidence": 0.7,
            }]
        except Exception as e:
            log.error(f"Cohere routing failed: {e}")
            return []

# -- Singleton ------------------------------------------------
router = Router()

# -- Test block -----------------------------------------------
if __name__ == "__main__":
    print("\n--- Router Test ---\n")
    
    test_queries = [
        "hello jarvis how are you",
        "open chrome",
        "close whatsapp",
        "play shape of you",
        "play despacito on spotify",
        "open vs code and open chrome",
        "search python tutorial on chrome",
        "search funny videos on youtube",
        "volume up",
        "take a screenshot",
        "generate image of sunset",
        "write a python web scraper on claude",
        "search elon musk news on chatgpt",
        "ask gemini about quantum computing",
        "what's the weather in pune",
        "latest news",
        "what is elon musk net worth",
        "switch to gaming mode",
        "activate security mode",
        "be my companion",
        "save personal data",
        "clear data",
        "exit",
    ]
    
    for q in test_queries:
        intents = router.route(q)
        if not intents:
            print(f"  '{q[:45]}' -> NO INTENT")
            continue
        
        for i, intent in enumerate(intents):
            prefix = "  " if i == 0 else "     "
            act = intent["action"]
            tgt = intent["target"][:30]
            params = intent.get("params", {})
            p_str = f" {params}" if params else ""
            print(f"{prefix}'{q[:45]:<45}' -> {act:15} | {tgt:30}{p_str}")
    
    print("\n[OK] Router test complete\n")