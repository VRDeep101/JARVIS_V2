# =============================================================
#  Backend/External/NewsEngine.py - NewsAPI.org
#
#  FREE tier: 100 requests/day
#
#  Usage:
#    from Backend.External.NewsEngine import news
#    news.top_headlines()           # India top 5
#    news.search("technology")      # search query
#    news.by_category("sports")
# =============================================================

from typing import Dict, List, Optional

import requests
from dotenv import dotenv_values

from Backend.Utils.Logger import get_logger
from Backend.Utils.InternetCheck import net

log = get_logger("News")

env = dotenv_values(".env")
API_KEY = env.get("NewsAPIKey", "").strip()

BASE_URL = "https://newsapi.org/v2"

CATEGORIES = ["business", "entertainment", "general", "health",
              "science", "sports", "technology"]

class NewsEngine:
    """NewsAPI wrapper."""
    
    def _check(self) -> Optional[Dict]:
        if not API_KEY or API_KEY == "paste_here":
            return {"ok": False, "message": "News API key not set, Sir."}
        if not net.is_online():
            return {"ok": False, "message": "No internet for news, Sir."}
        return None
    
    def top_headlines(self, country: str = "in", count: int = 5) -> Dict:
        """Top headlines from country (default India)."""
        err = self._check()
        if err:
            return err
        
        count = max(1, min(10, count))
        
        try:
            response = requests.get(
                f"{BASE_URL}/top-headlines",
                params={"country": country, "apiKey": API_KEY, "pageSize": count},
                timeout=10,
            )
            
            if response.status_code != 200:
                return {"ok": False, "message": f"News API error: {response.status_code}"}
            
            data = response.json()
            articles = data.get("articles", [])
            
            if not articles:
                return {"ok": True, "count": 0, "message": "No headlines right now, Sir.",
                        "articles": []}
            
            # Extract clean list
            clean = []
            for a in articles[:count]:
                clean.append({
                    "title": a.get("title", "").split(" - ")[0],  # strip source suffix
                    "source": a.get("source", {}).get("name", ""),
                    "description": a.get("description", ""),
                    "url": a.get("url", ""),
                    "published": a.get("publishedAt", "")[:10],
                })
            
            # Summary
            summary = self._build_summary(clean, count)
            
            return {
                "ok": True,
                "count": len(clean),
                "articles": clean,
                "summary": summary,
                "message": summary,
            }
        
        except requests.Timeout:
            return {"ok": False, "message": "News request timed out, Sir."}
        except Exception as e:
            log.error(f"News error: {e}")
            return {"ok": False, "message": f"News fetch failed: {str(e)[:60]}"}
    
    def by_category(self, category: str, country: str = "in") -> Dict:
        """News by category."""
        if category.lower() not in CATEGORIES:
            return {"ok": False, "message": f"Unknown category. Try: {', '.join(CATEGORIES)}"}
        
        err = self._check()
        if err:
            return err
        
        try:
            response = requests.get(
                f"{BASE_URL}/top-headlines",
                params={
                    "country": country,
                    "category": category.lower(),
                    "apiKey": API_KEY,
                    "pageSize": 5,
                },
                timeout=10,
            )
            
            if response.status_code != 200:
                return {"ok": False, "message": f"News API error: {response.status_code}"}
            
            data = response.json()
            articles = data.get("articles", [])[:5]
            
            if not articles:
                return {"ok": True, "count": 0,
                        "message": f"No {category} news found, Sir.", "articles": []}
            
            clean = [{"title": a.get("title", "").split(" - ")[0],
                      "source": a.get("source", {}).get("name", "")}
                     for a in articles]
            
            titles = ". ".join(a["title"] for a in clean[:3])
            return {
                "ok": True,
                "count": len(clean),
                "articles": clean,
                "message": f"Top {category} news, Sir: {titles}.",
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def search(self, query: str, count: int = 5) -> Dict:
        """Search news by keyword."""
        err = self._check()
        if err:
            return err
        
        if not query or len(query) < 2:
            return {"ok": False, "message": "Need a search query, Sir."}
        
        try:
            response = requests.get(
                f"{BASE_URL}/everything",
                params={
                    "q": query,
                    "apiKey": API_KEY,
                    "pageSize": count,
                    "sortBy": "publishedAt",
                    "language": "en",
                },
                timeout=10,
            )
            
            if response.status_code != 200:
                return {"ok": False, "message": f"News search failed: {response.status_code}"}
            
            data = response.json()
            articles = data.get("articles", [])[:count]
            
            if not articles:
                return {"ok": True, "count": 0,
                        "message": f"No results for '{query}', Sir.", "articles": []}
            
            clean = [{
                "title": a.get("title", "").split(" - ")[0],
                "source": a.get("source", {}).get("name", ""),
                "description": a.get("description", ""),
            } for a in articles]
            
            summary = self._build_summary(clean, 3)
            return {
                "ok": True,
                "count": len(clean),
                "articles": clean,
                "message": f"Top results for {query}: {summary}",
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}
    
    def _build_summary(self, articles: List[Dict], n: int = 3) -> str:
        """Spoken-friendly top-N summary."""
        if not articles:
            return "No headlines available."
        
        parts = []
        for i, a in enumerate(articles[:n], 1):
            title = a.get("title", "")
            if title:
                parts.append(f"{i}. {title}")
        
        return " ".join(parts) + "."

# Singleton
news = NewsEngine()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- NewsEngine Test ---\n")
    
    if not API_KEY or API_KEY == "paste_here":
        print("[WARN] NewsAPIKey not set. Get it from https://newsapi.org")
    else:
        print("-- Top 3 headlines (India) --")
        r = news.top_headlines(count=3)
        if r["ok"]:
            for i, a in enumerate(r["articles"][:3], 1):
                print(f"  {i}. [{a['source']}] {a['title']}")
        else:
            print(f"  {r['message']}")
        
        print("\n-- Technology category --")
        r = news.by_category("technology")
        print(f"  {r['message'][:200]}")
    
    print("\n[OK] NewsEngine test complete\n")