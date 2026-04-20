# =============================================================
#  Backend/External/RealtimeSearchEngine.py - Web Search + Wiki
#
#  Kya karta:
#    - DuckDuckGo web search (no API key)
#    - Wikipedia fallback for encyclopedic queries
#    - Sends results to Groq LLM for summarization
#    - Always returns English answer
#    - Fresh every time (no stale cache)
#
#  Usage:
#    from Backend.External.RealtimeSearchEngine import rts
#    answer = rts.ask("what is elon musk net worth")
# =============================================================

import datetime
import re
import time
from typing import Dict, List, Optional

from dotenv import dotenv_values

from Backend.Utils.Logger import get_logger
from Backend.Utils.InternetCheck import net

log = get_logger("RealtimeSearch")

env = dotenv_values(".env")
GROQ_KEY = env.get("GroqAPIKey", "").strip()

# -- Optional deps --------------------------------------------
try:
    from ddgs import DDGS
    DDGS_OK = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        DDGS_OK = True
    except ImportError:
        DDGS_OK = False

try:
    import wikipedia
    wikipedia.set_lang("en")
    WIKI_OK = True
except ImportError:
    WIKI_OK = False

try:
    from groq import Groq
    GROQ_PKG_OK = True
except ImportError:
    GROQ_PKG_OK = False

# -- Groq client ----------------------------------------------
_groq = None
def _get_groq():
    global _groq
    if _groq is None and GROQ_PKG_OK and GROQ_KEY:
        try:
            _groq = Groq(api_key=GROQ_KEY)
        except Exception as e:
            log.error(f"Groq init: {e}")
    return _groq

# -- Wiki triggers --------------------------------------------
WIKI_TRIGGERS = [
    "who is", "who was", "what is", "what are", "history of",
    "born in", "biography", "founder of", "invented", "discovered",
    "capital of", "population of", "located in", "meaning of",
    "definition of", "explain", "how does", "why does",
]

SYSTEM_PROMPT = """You are Jarvis, an intelligent assistant.

Rules:
- ALWAYS reply in English only.
- Use the search results below as your PRIMARY source.
- Give direct, specific answers with real numbers/names/dates.
- Keep replies concise: 2-4 sentences for simple facts.
- NEVER say "as of my knowledge" or "I don't have real-time access" - results are provided.
- If results don't have the answer, say so honestly.
- Sound like a smart friend, not a search engine."""

class RealtimeSearch:
    """Web search + Wikipedia + LLM summarization."""
    
    def _should_use_wiki(self, query: str) -> bool:
        q = query.lower()
        return any(t in q for t in WIKI_TRIGGERS)
    
    def web_search(self, query: str, max_results: int = 6) -> str:
        """DuckDuckGo search. Returns formatted results string."""
        if not DDGS_OK:
            return "Search engine unavailable."
        
        if not net.is_online():
            return "No internet connection."
        
        for attempt in range(3):
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(
                        query,
                        max_results=max_results,
                        region="in-en",
                        safesearch="off",
                    ))
                
                if not results:
                    return "No search results found."
                
                lines = []
                for i, r in enumerate(results, 1):
                    title = r.get("title", "").strip()
                    body = r.get("body", "").strip()
                    source = r.get("href", "").strip()
                    if title or body:
                        lines.append(f"[{i}] {title}\n{body}\nSource: {source}")
                
                return "\n\n".join(lines)
            except Exception as e:
                if attempt < 2:
                    time.sleep(1)
                else:
                    log.error(f"Search fail: {e}")
                    return f"Search failed: {e}"
        return "Search unavailable."
    
    def wikipedia_search(self, query: str) -> str:
        """Fetch Wikipedia summary."""
        if not WIKI_OK:
            return ""
        
        try:
            results = wikipedia.search(query, results=1)
            if not results:
                return ""
            summary = wikipedia.summary(results[0], sentences=3, auto_suggest=False)
            return f"Wikipedia ({results[0]}): {summary}"
        except wikipedia.exceptions.DisambiguationError as e:
            # Try first option
            try:
                summary = wikipedia.summary(e.options[0], sentences=2, auto_suggest=False)
                return f"Wikipedia ({e.options[0]}): {summary}"
            except Exception:
                return ""
        except Exception as e:
            log.debug(f"Wiki error: {e}")
            return ""
    
    # =========================================================
    #  MAIN: ASK
    # =========================================================
    def ask(self, query: str) -> Dict:
        """Search + LLM synthesize. Always English reply."""
        if not query or not query.strip():
            return {"ok": False, "message": "No query given."}
        
        if not net.is_online():
            return {"ok": False, "message": "No internet, Sir."}
        
        log.info(f"Searching: {query[:50]}")
        
        # Fresh web search
        search_results = self.web_search(query)
        
        # Optional Wikipedia
        wiki_data = ""
        if self._should_use_wiki(query):
            wiki_data = self.wikipedia_search(query)
        
        # Build LLM prompt
        now = datetime.datetime.now()
        context = f"""[CURRENT DATE/TIME]
{now:%A, %d %B %Y, %H:%M}

[WEB SEARCH RESULTS]
{search_results}
"""
        if wiki_data:
            context += f"\n[WIKIPEDIA]\n{wiki_data}\n"
        
        context += f"\n[USER QUERY]\n{query}\n\nAnswer in English, using above results."
        
        # Groq synthesize
        client = _get_groq()
        if not client:
            # Fallback: raw search first result
            if search_results and len(search_results) > 30:
                first = search_results.split("\n\n")[0]
                return {
                    "ok": True,
                    "message": first[:300],
                    "raw_search": search_results[:500],
                }
            return {"ok": False, "message": "LLM unavailable, Sir."}
        
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context},
                ],
                temperature=0.4,
                max_tokens=500,
                stream=False,
            )
            answer = completion.choices[0].message.content.strip()
            answer = re.sub(r"</s>$", "", answer).strip()
            
            return {
                "ok": True,
                "query": query,
                "answer": answer,
                "message": answer,
                "used_wiki": bool(wiki_data),
            }
        except Exception as e:
            log.error(f"LLM synthesize error: {e}")
            return {"ok": False, "message": "Couldn't synthesize results, Sir."}

# Singleton
rts = RealtimeSearch()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- RealtimeSearchEngine Test ---\n")
    
    print(f"DDGS      : {DDGS_OK}")
    print(f"Wikipedia : {WIKI_OK}")
    print(f"Groq      : {bool(GROQ_KEY and GROQ_KEY != 'paste_here')}")
    print()
    
    if net.is_online() and DDGS_OK and GROQ_KEY and GROQ_KEY != "paste_here":
        tests = [
            "what is elon musk net worth",
            "who won the last IPL",
            "capital of japan",
        ]
        for q in tests:
            print(f"Q: {q}")
            r = rts.ask(q)
            print(f"A: {r.get('message', 'failed')[:200]}\n")
    else:
        print("[INFO] Need internet + Groq key for full test")
    
    print("[OK] RealtimeSearchEngine test complete\n")