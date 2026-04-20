# =============================================================
#  Backend/External/WolframSolver.py - Math/Science Queries
#
#  FREE: 2000 calls/month
#
#  Usage:
#    from Backend.External.WolframSolver import wolfram
#    wolfram.ask("integral of x^2")
#    wolfram.ask("what is the mass of moon")
# =============================================================

from typing import Dict, Optional

from dotenv import dotenv_values

from Backend.Utils.Logger import get_logger
from Backend.Utils.InternetCheck import net

log = get_logger("Wolfram")

env = dotenv_values(".env")
API_KEY = env.get("WolframAPIKey", "").strip()

try:
    import wolframalpha
    WOLFRAM_OK = True
except ImportError:
    WOLFRAM_OK = False

_client = None

def _get_client():
    global _client
    if _client is None and WOLFRAM_OK and API_KEY and API_KEY != "paste_here":
        try:
            _client = wolframalpha.Client(API_KEY)
        except Exception as e:
            log.error(f"Wolfram init error: {e}")
    return _client

class WolframSolver:
    """Wolfram Alpha wrapper for math/science questions."""
    
    def ask(self, query: str) -> Dict:
        """Query Wolfram Alpha."""
        if not WOLFRAM_OK:
            return {"ok": False, "message": "wolframalpha package not installed, Sir."}
        
        if not API_KEY or API_KEY == "paste_here":
            return {"ok": False, "message": "Wolfram API key not set, Sir."}
        
        if not net.is_online():
            return {"ok": False, "message": "No internet, Sir."}
        
        client = _get_client()
        if not client:
            return {"ok": False, "message": "Wolfram client unavailable, Sir."}
        
        try:
            res = client.query(query)
            
            # Extract plaintext results
            answer = None
            pods_data = []
            
            try:
                for pod in res.pods:
                    pod_title = getattr(pod, "title", "")
                    subpods = getattr(pod, "subpods", [])
                    
                    if not isinstance(subpods, list):
                        subpods = [subpods]
                    
                    for sp in subpods:
                        text = getattr(sp, "plaintext", "")
                        if text:
                            pods_data.append({"title": pod_title, "text": text})
                            # Prefer "Result" or primary pod
                            if answer is None and pod_title.lower() in ("result", "results", "decimal approximation", "value"):
                                answer = text
                
                # Fallback: use first pod result
                if answer is None and pods_data:
                    answer = pods_data[0]["text"]
            except Exception as e:
                log.debug(f"Pod iteration error: {e}")
            
            if not answer:
                return {"ok": False, "message": f"No answer found for '{query}', Sir."}
            
            # Clean answer for speech
            answer_clean = answer.replace("≈", "approximately ").replace("×10^", " times 10 to the ")
            
            return {
                "ok": True,
                "query": query,
                "answer": answer_clean,
                "all_pods": pods_data[:5],
                "message": f"{answer_clean}",
            }
        
        except StopIteration:
            return {"ok": False, "message": f"Wolfram didn't understand '{query}', Sir."}
        except Exception as e:
            log.error(f"Wolfram error: {e}")
            return {"ok": False, "message": f"Wolfram query failed: {str(e)[:60]}"}

# Singleton
wolfram = WolframSolver()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- WolframSolver Test ---\n")
    
    print(f"wolframalpha installed: {WOLFRAM_OK}")
    print(f"API key set: {bool(API_KEY and API_KEY != 'paste_here')}")
    
    if WOLFRAM_OK and API_KEY and API_KEY != "paste_here":
        tests = [
            "integral of x^2",
            "mass of moon",
            "speed of light in km/s",
            "population of India",
        ]
        for q in tests:
            r = wolfram.ask(q)
            print(f"\n  Q: {q}")
            print(f"  A: {r.get('message', 'failed')[:120]}")
    else:
        print("[INFO] Get key from https://products.wolframalpha.com/api")
    
    print("\n[OK] WolframSolver test complete\n")