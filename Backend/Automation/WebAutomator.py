# =============================================================
#  Backend/Automation/WebAutomator.py - Claude/ChatGPT/Gemini
#
#  Kya karta:
#    - Opens Chrome with JarvisAI profile (side-screen visible)
#    - Navigates to Claude/ChatGPT/Gemini
#    - Types query visibly (user watches)
#    - Waits for AI response to complete
#    - Reads response back, truncates for speech
#    - Auto-fallback across services if one fails
#    - Login detection (60-sec grace period)
#
#  Routing:
#    Code-related  -> Claude
#    Content/image -> ChatGPT
#    Backup        -> Gemini
#
#  Usage:
#    from Backend.Automation.WebAutomator import web_ai
#    result = web_ai.ask(
#        query="write a python web scraper",
#        preferred="claude",
#        on_status=lambda m: tts.say(m)
#    )
#    print(result["speech_text"])
# =============================================================

import os
import time
from typing import Optional, Callable, Dict, List

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths

log = get_logger("WebAutomator")

# -- Selenium imports (lazy-style) ----------------------------
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

# =============================================================
#  Chrome profile for AI automation
# =============================================================
CHROME_USER_DATA = str(paths.CHROME_USER_DATA)
JARVIS_PROFILE   = "JarvisAI"   # separate profile - created on first run

# =============================================================
#  AI site configurations
# =============================================================
AI_SITES = {
    "claude": {
        "name": "Claude",
        "url": "https://claude.ai/new",
        "input_selectors": [
            "div[contenteditable='true'][data-placeholder]",
            "div.ProseMirror",
            "div[contenteditable='true']",
        ],
        "response_selectors": [
            ".font-claude-message",
            "[data-testid='chat-message-content']",
            "div.prose",
        ],
        "stop_selectors": [
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
        ],
        "login_markers": ["login", "onboarding", "signin", "sign-in"],
        "max_wait": 90,
    },
    "chatgpt": {
        "name": "ChatGPT",
        "url": "https://chatgpt.com/",
        "input_selectors": [
            "#prompt-textarea",
            "div#prompt-textarea",
            "textarea[placeholder]",
        ],
        "response_selectors": [
            "[data-message-author-role='assistant'] .markdown",
            ".markdown.prose",
            "[data-message-author-role='assistant']",
        ],
        "stop_selectors": [
            "button[data-testid='stop-button']",
            "button[aria-label*='Stop']",
        ],
        "login_markers": ["auth/login", "login", "accounts.openai", "chatgpt.com/auth"],
        "max_wait": 90,
    },
    "gemini": {
        "name": "Gemini",
        "url": "https://gemini.google.com/app",
        "input_selectors": [
            ".ql-editor[contenteditable='true']",
            "rich-textarea .ql-editor",
            "div[contenteditable='true']",
        ],
        "response_selectors": [
            "model-response .response-content",
            ".response-content",
            "message-content",
        ],
        "stop_selectors": [
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
        ],
        "login_markers": ["accounts.google.com"],
        "max_wait": 90,
    },
}

# =============================================================
#  Routing keywords
# =============================================================
CODE_KEYWORDS = [
    "code", "program", "script", "function", "class", "algorithm",
    "debug", "fix bug", "python", "javascript", "java", "c++",
    "html", "css", "sql", "api", "implement", "build app",
    "website", "app banao", "error fix",
]
CONTENT_KEYWORDS = [
    "write", "essay", "article", "blog", "story", "email", "letter",
    "content", "post", "caption", "summary", "paragraph",
    "image", "design", "thumbnail",
]

def _route(query: str) -> str:
    """Auto-route based on keywords."""
    q = query.lower()
    code_score = sum(1 for k in CODE_KEYWORDS if k in q)
    content_score = sum(1 for k in CONTENT_KEYWORDS if k in q)
    
    if code_score > content_score and code_score > 0:
        return "claude"
    if content_score > 0:
        return "chatgpt"
    return "chatgpt"  # default

# =============================================================
#  WebAutomator class
# =============================================================
class WebAutomator:
    """Opens AI web services and interacts visibly."""
    
    def __init__(self):
        self.driver = None
    
    # -- Driver management -----------------------------------
    def _make_driver(self):
        """Create Chrome driver with JarvisAI profile, side-window positioned."""
        if not SELENIUM_OK:
            raise RuntimeError("Selenium not installed")
        
        opts = Options()
        opts.add_argument(f"--user-data-dir={CHROME_USER_DATA}")
        opts.add_argument(f"--profile-directory={JARVIS_PROFILE}")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        
        # Side-screen positioning (right half of typical 1920px screen)
        opts.add_argument("--window-position=960,0")
        opts.add_argument("--window-size=960,1040")
        
        try:
            driver = webdriver.Chrome(options=opts)
        except Exception:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=opts,
            )
        
        # Hide automation marker
        driver.execute_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        return driver
    
    def _ensure_driver(self):
        """Lazy create driver."""
        if self.driver is None:
            log.info("Starting Chrome (JarvisAI profile)...")
            self.driver = self._make_driver()
    
    def close(self):
        """Quit the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
    
    # -- Login detection -------------------------------------
    def _is_login_page(self, cfg: Dict) -> bool:
        try:
            url = self.driver.current_url.lower()
            return any(m in url for m in cfg["login_markers"])
        except Exception:
            return False
    
    # -- Input finding ---------------------------------------
    def _find_input(self, selectors: List[str], timeout: int = 15):
        """Try each selector until one works."""
        for sel in selectors:
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
            except Exception:
                pass
        # JS fallback
        for sel in selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    return el
            except Exception:
                pass
        return None
    
    # -- Type query visibly ----------------------------------
    def _type_query(self, element, query: str):
        """Type into contenteditable or textarea - visible to user."""
        element.click()
        time.sleep(0.4)
        try:
            # contenteditable (Claude, Gemini)
            self.driver.execute_script("""
                arguments[0].focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, arguments[1]);
            """, element, query)
        except Exception:
            # Regular textarea (ChatGPT)
            element.clear()
            element.send_keys(query)
        time.sleep(0.4)
        element.send_keys(Keys.RETURN)
    
    # -- Wait for response ----------------------------------
    def _wait_response(self, cfg: Dict) -> str:
        """Wait for AI to finish, then extract response text."""
        stop_sels = cfg["stop_selectors"]
        resp_sels = cfg["response_selectors"]
        max_wait = cfg["max_wait"]
        
        # Phase 1: Stop button appears = AI started
        appeared = False
        t0 = time.time()
        while time.time() - t0 < 15:
            for s in stop_sels:
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, s)
                    if btns and btns[0].is_displayed():
                        appeared = True
                        break
                except Exception:
                    pass
            if appeared:
                break
            time.sleep(0.5)
        
        # Phase 2: Stop button gone = AI done
        if appeared:
            t0 = time.time()
            while time.time() - t0 < max_wait:
                try:
                    all_gone = all(
                        not any(
                            e.is_displayed()
                            for e in self.driver.find_elements(By.CSS_SELECTOR, s)
                        )
                        for s in stop_sels
                    )
                    if all_gone:
                        break
                except Exception:
                    pass
                time.sleep(1)
        else:
            # Fallback: text stability check
            prev = ""
            stable = 0
            t0 = time.time()
            while time.time() - t0 < max_wait:
                for s in resp_sels:
                    try:
                        els = self.driver.find_elements(By.CSS_SELECTOR, s)
                        if els:
                            curr = els[-1].text.strip()
                            if curr and curr == prev:
                                stable += 1
                                if stable >= 3:
                                    return curr
                            elif curr:
                                prev = curr
                                stable = 0
                            break
                    except Exception:
                        pass
                time.sleep(2)
        
        time.sleep(1.2)
        
        # Final extraction - take LAST message
        for s in resp_sels:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, s)
                if els:
                    txt = els[-1].text.strip()
                    if txt:
                        return txt
            except Exception:
                pass
        return ""
    
    # -- Speech truncation ----------------------------------
    def _truncate_for_speech(self, text: str, max_words: int = 80) -> str:
        """Truncate long responses for TTS."""
        words = text.split()
        if len(words) <= max_words:
            return text
        truncated = " ".join(words[:max_words])
        return truncated + "... Full response is on screen, Sir."
    
    # =========================================================
    #  MAIN: ask
    # =========================================================
    def ask(
        self,
        query: str,
        preferred: Optional[str] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Dict:
        """
        Open AI site, send query, read response.
        
        Args:
            query: The question/task
            preferred: "claude" | "chatgpt" | "gemini" (optional)
            on_status: callback(msg) for status updates
        
        Returns:
            {
                "ok": bool,
                "pre_message": str,   # say before browser opens
                "response": str,      # full AI response
                "speech_text": str,   # truncated for speech
                "ai_used": str,       # "Claude" / "ChatGPT" / "Gemini"
                "error": str,
            }
        """
        if not SELENIUM_OK:
            return {
                "ok": False,
                "error": "Selenium not installed",
                "response": "",
                "speech_text": "Sir, web automation isn't available right now.",
                "ai_used": "",
                "pre_message": "",
            }
        
        status = on_status or (lambda m: log.info(m))
        
        # Determine order
        if preferred and preferred.lower() in AI_SITES:
            primary = preferred.lower()
        else:
            primary = _route(query)
        
        others = [k for k in AI_SITES if k != primary]
        order = [primary] + others
        
        result = {
            "ok": False,
            "pre_message": f"Opening {AI_SITES[primary]['name']} for the best output, Sir. Please wait.",
            "response": "",
            "speech_text": "",
            "ai_used": "",
            "error": "",
        }
        
        for idx, ai_key in enumerate(order):
            cfg = AI_SITES[ai_key]
            
            if idx > 0:
                status(f"Switching to {cfg['name']} due to a connection issue, Sir.")
            
            try:
                self._ensure_driver()
                
                self.driver.get(cfg["url"])
                time.sleep(3)
                
                # Login check
                if self._is_login_page(cfg):
                    status(
                        f"Sir, sign-in required on {cfg['name']}. "
                        f"Please log in. I'll wait up to 60 seconds."
                    )
                    t0 = time.time()
                    while time.time() - t0 < 60 and self._is_login_page(cfg):
                        time.sleep(2)
                    if self._is_login_page(cfg):
                        status(f"{cfg['name']} login timeout. Trying next service.")
                        continue
                    self.driver.get(cfg["url"])
                    time.sleep(3)
                
                # Find input box
                inp = self._find_input(cfg["input_selectors"], timeout=15)
                if not inp:
                    status(f"Couldn't find input box on {cfg['name']}. Next service.")
                    continue
                
                # Type query (visible!)
                self._type_query(inp, query)
                status(f"{cfg['name']} is processing, Sir. One moment.")
                
                # Wait for response
                resp = self._wait_response(cfg)
                
                if resp and len(resp) > 15:
                    result["ok"] = True
                    result["response"] = resp
                    result["speech_text"] = self._truncate_for_speech(resp)
                    result["ai_used"] = cfg["name"]
                    return result
                else:
                    status(f"No valid response from {cfg['name']}. Trying next.")
                    continue
            
            except (WebDriverException,) as e:
                status(f"Browser issue on {cfg['name']}. Trying next service.")
                self.close()
            
            except Exception as e:
                log.error(f"{cfg['name']} error: {e}")
                status(f"Error with {cfg['name']}. Trying next.")
        
        if not result["ok"]:
            result["error"] = (
                "All AI services failed. Check internet and make sure "
                "you're logged in to the JarvisAI Chrome profile."
            )
            result["speech_text"] = (
                "Sir, all AI services failed. Check internet and login."
            )
        
        return result

# =============================================================
#  Singleton
# =============================================================
web_ai = WebAutomator()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- WebAutomator Test ---\n")
    
    if not SELENIUM_OK:
        print("[ERR] Selenium not installed. Run: pip install selenium")
    else:
        print("-- Routing test --")
        tests = [
            "write a python web scraper",      # -> claude
            "write a blog post about AI",       # -> chatgpt
            "explain quantum computing",        # -> chatgpt (default)
            "fix this javascript bug",          # -> claude
        ]
        for q in tests:
            r = _route(q)
            print(f"  '{q[:40]:<40}' -> {r}")
        
        print("\n-- Chrome profile info --")
        print(f"  User data path: {CHROME_USER_DATA}")
        print(f"  Jarvis profile: {JARVIS_PROFILE}")
        
        print("\n-- Manual live test --")
        print("  Uncomment the live test below to actually open Chrome")
        print("  and send a query to Claude/ChatGPT.")
        
        # Uncomment for live test:
        # def status_cb(msg):
        #     print(f"  [STATUS] {msg}")
        # 
        # result = web_ai.ask(
        #     "Write a simple hello world in Python",
        #     preferred="claude",
        #     on_status=status_cb,
        # )
        # print(f"\n  OK      : {result['ok']}")
        # print(f"  AI Used : {result['ai_used']}")
        # print(f"  Speech  : {result['speech_text'][:150]}")
        # print(f"  Error   : {result.get('error', '')}")
        # web_ai.close()
    
    print("\n[OK] WebAutomator test complete\n")