# =============================================================
#  Backend/Voice/SpeechToText.py - Voice Input
#
#  Kya karta:
#    - Chrome Web Speech API via hidden browser window
#    - Wake word "Jarvis" required for every command
#    - Echo-proof: mic OFF while TTS speaking
#    - Auto-correction (harvis -> jarvis, etc)
#    - Fuzzy matching for tough mishears
#    - Short/garbled input filter
#    - Self-echo final check (via ContextManager)
#    - Interrupt detection ("Jarvis stop" / "Jarvis wait")
#    - 3-state: Listen -> Think -> Speak
#
#  Usage:
#    from Backend.Voice.SpeechToText import stt
#    query = stt.listen()   -> blocks until valid command
# =============================================================

import http.server
import os
import socketserver
import threading
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import dotenv_values

try:
    import mtranslate
    MTRANSLATE_OK = True
except ImportError:
    MTRANSLATE_OK = False

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Voice.PronunciationFixer import correct_stt_text, fuzzy_match_jarvis
from Backend.Voice import TextToSpeech as tts_module
from Backend.Core.ContextManager import context

log = get_logger("STT")

# -- Config ---------------------------------------------------
env = dotenv_values(".env")
INPUT_LANG = env.get("InputLanguage", "en-IN")

WAKE_WORD = "jarvis"
INTERRUPT_WORDS = ["stop", "wait", "pause", "shut up", "quiet", "ruk", "chup"]

MIN_WORDS = 1
MIN_CHARS = 3
POST_SPEAK_BUFFER = 0.8

HTTP_PORT = 9876

# -- Paths ----------------------------------------------------
VOICE_HTML_PATH = paths.DATA_DIR / "Voice.html"

# =============================================================
#  VOICE.HTML (local Web Speech API page)
# =============================================================
VOICE_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head><title>Jarvis STT</title></head>
<body>
<button id="start" onclick="startRecognition()">Start</button>
<button id="end" onclick="stopRecognition()">Stop</button>
<p id="output"></p>
<p id="confidence"></p>
<script>
const output = document.getElementById('output');
const confidence = document.getElementById('confidence');
let recognition;

function startRecognition() {{
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = '{INPUT_LANG}';
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.maxAlternatives = 3;
    recognition._stopped = false;
    
    recognition.onresult = function(event) {{
        const result = event.results[event.results.length - 1];
        if (result.isFinal) {{
            output.textContent = result[0].transcript.trim();
            confidence.textContent = result[0].confidence.toFixed(2);
        }}
    }};
    
    recognition.onend = function() {{
        if (!recognition._stopped) {{
            try {{ recognition.start(); }} catch(e) {{}}
        }}
    }};
    
    recognition.onerror = function(event) {{
        if (event.error !== 'no-speech') {{
            output.textContent = '';
            confidence.textContent = '0';
        }}
    }};
    
    try {{ recognition.start(); }} catch(e) {{}}
}}

function stopRecognition() {{
    if (recognition) {{
        recognition._stopped = true;
        try {{ recognition.stop(); }} catch(e) {{}}
    }}
    output.textContent = '';
    confidence.textContent = '0';
}}
</script>
</body>
</html>"""

# =============================================================
#  Local HTTP server (serves Voice.html)
# =============================================================
_SERVER_DIR = str(paths.DATA_DIR)

class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=_SERVER_DIR, **kwargs)
    def log_message(self, format, *args):
        pass  # silence

class _ReusingTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        """Suppress noisy connection-reset errors from Chrome closing on shutdown."""
        import sys
        exc_type = sys.exc_info()[0]
        if exc_type in (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass  # Chrome closed the connection — expected on shutdown, not an error
        else:
            super().handle_error(request, client_address)

def _start_http_server():
    try:
        with _ReusingTCPServer(("", HTTP_PORT), _QuietHandler) as httpd:
            httpd.serve_forever()
    except OSError as e:
        log.error(f"HTTP server port {HTTP_PORT} failed: {e}")

# =============================================================
#  STT class
# =============================================================
class STT:
    """Speech-to-text with echo filter and smart corrections."""
    
    def __init__(self):
        self.driver = None
        self.mic_running = False
        self._http_thread = None
        self._ready = False
    
    def initialize(self):
        """One-time setup: HTTP server + Chrome headless STT window."""
        if self._ready:
            return
        
        # Write HTML file
        try:
            with open(VOICE_HTML_PATH, "w", encoding="utf-8") as f:
                f.write(VOICE_HTML)
        except Exception as e:
            log.error(f"Voice.html write error: {e}")
            raise
        
        # Start HTTP server
        self._http_thread = threading.Thread(
            target=_start_http_server, daemon=True, name="STT_HTTP"
        )
        self._http_thread.start()
        time.sleep(0.3)
        
        # Start Chrome (headless-ish)
        log.info("Initializing STT Chrome driver...")
        opts = Options()
        opts.add_argument("--use-fake-ui-for-media-stream")
        opts.add_argument("--allow-file-access-from-files")
        opts.add_argument("--window-position=-32000,-32000")  # offscreen
        opts.add_argument("--window-size=1,1")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-software-rasterizer")
        opts.add_argument("--mute-audio")
        opts.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=opts,
            )
            self.driver.get(f"http://localhost:{HTTP_PORT}/Voice.html")
            time.sleep(1.0)
            self._ready = True
            log.success(f"STT ready | wake word: '{WAKE_WORD}'")
        except Exception as e:
            log.error(f"Chrome init failed: {e}")
            raise
    
    # -- Chrome element helpers ----------------------------
    def _clear_output(self):
        if not self.driver:
            return
        try:
            self.driver.execute_script(
                "document.getElementById('output').textContent = '';"
            )
        except Exception:
            pass
    
    def _get_text(self) -> str:
        if not self.driver:
            return ""
        try:
            return self.driver.find_element(By.ID, "output").text.strip()
        except Exception:
            return ""
    
    def _start_recognition(self):
        if not self.driver:
            return False
        try:
            self.driver.find_element(By.ID, "start").click()
            self.mic_running = True
            return True
        except Exception as e:
            log.error(f"Start recognition error: {e}")
            return False
    
    def _stop_recognition(self):
        if not self.driver:
            return
        try:
            self.driver.find_element(By.ID, "end").click()
        except Exception:
            pass
        self.mic_running = False
    
    def _ensure_mic_off(self):
        if self.mic_running:
            self._stop_recognition()
            self._clear_output()
    
    def _ensure_mic_on(self):
        if not self.mic_running:
            self._clear_output()
            self._start_recognition()
    
    # -- Wait for TTS to finish ----------------------------
    def _wait_for_tts(self):
        """Block while TTS is speaking. Mic stays off."""
        self._ensure_mic_off()
        while tts_module.is_speaking():
            time.sleep(0.03)
        time.sleep(POST_SPEAK_BUFFER)
        self._clear_output()
    
    # -- Helpers ------------------------------------------
    def _is_meaningful(self, text: str) -> bool:
        """Filter short/garbled input."""
        t = text.strip()
        if len(t) < MIN_CHARS:
            return False
        words = t.split()
        if len(words) < MIN_WORDS:
            return False
        # Single very short word = probably noise
        if len(words) == 1 and len(words[0]) <= 2:
            return False
        return True
    
    def _translate(self, text: str) -> str:
        """Translate non-English to English."""
        if not MTRANSLATE_OK:
            return text
        try:
            result = mtranslate.translate(text, "en", "auto")
            if result and result.strip():
                return result.strip()
        except Exception:
            pass
        return text
    
    def _contains_wake(self, text: str) -> bool:
        """True if wake word present (with fuzzy match)."""
        lower = text.lower()
        if WAKE_WORD in lower:
            return True
        # Fuzzy match
        return fuzzy_match_jarvis(text)
    
    def _extract_command(self, text: str) -> str:
        """Extract command after wake word."""
        lower = text.lower()
        idx = lower.find(WAKE_WORD)
        if idx == -1:
            # Check fuzzy
            words = text.split()
            for i, w in enumerate(words):
                w_clean = w.lower().strip(".,!?")
                if w_clean == WAKE_WORD or fuzzy_match_jarvis(w_clean):
                    after = " ".join(words[i+1:])
                    return after.strip(" ,.!?-")
            return ""
        return text[idx + len(WAKE_WORD):].strip(" ,.!?-")
    
    def _is_interrupt(self, text: str) -> bool:
        """Check if user wants to interrupt Jarvis."""
        t = text.lower().strip()
        for w in INTERRUPT_WORDS:
            if w in t and len(t.split()) <= 3:
                return True
        return False
    
    def _modify_query(self, query: str) -> str:
        """Normalize final query (capitalize, punctuate)."""
        q = query.strip()
        if not q:
            return query
        # Capitalize first letter
        q = q[0].upper() + q[1:] if len(q) > 1 else q.upper()
        # Strip trailing punctuation variations
        while q and q[-1] in ".?!":
            q = q[:-1]
        
        # Add ? for questions
        question_starters = ["what", "who", "where", "when", "why", "how", "which",
                            "is", "are", "do", "does", "did", "will", "would",
                            "could", "should", "can"]
        first_word = q.lower().split()[0] if q.split() else ""
        if first_word in question_starters:
            q += "?"
        else:
            q += "."
        return q
    
    # =========================================================
    #  MAIN: listen loop
    # =========================================================
    def listen(self) -> Optional[str]:
        """
        Main listening loop.
        Returns valid command string when heard, or None if stopped.
        Blocks until a recognized command arrives.
        """
        if not self._ready:
            self.initialize()
        
        # If TTS is speaking, wait it out first
        if tts_module.is_speaking():
            self._wait_for_tts()
        
        self._ensure_mic_on()
        
        while True:
            # If TTS kicks in mid-wait, pause mic
            if tts_module.is_speaking():
                self._wait_for_tts()
                self._ensure_mic_on()
                continue
            
            raw = self._get_text()
            if not raw:
                time.sleep(0.05)
                continue
            
            self._ensure_mic_off()
            
            # 1. Auto-correct common mishears
            raw, was_corrected = correct_stt_text(raw)
            
            # 2. Filter short/noisy input
            if not self._is_meaningful(raw):
                log.debug(f"Filtered short input: '{raw}'")
                self._ensure_mic_on()
                continue
            
            # 3. Context-aware self-echo check
            if context.is_self_echo(raw):
                log.debug(f"Echo filtered: '{raw[:50]}'")
                self._ensure_mic_on()
                continue
            
            # 4. Translate if non-English
            if "en" not in INPUT_LANG.lower():
                raw = self._translate(raw)
            else:
                # Optional translation if mixed language detected
                translated = self._translate(raw)
                if translated and translated.strip() != raw.strip():
                    raw = translated
            
            # 5. Wake word check
            if not self._contains_wake(raw):
                log.debug(f"No wake word: '{raw[:50]}'")
                self._ensure_mic_on()
                continue
            
            # 6. Extract command after wake word
            command = self._extract_command(raw)
            if not command:
                log.debug("Wake word heard but no command")
                self._ensure_mic_on()
                continue
            
            # 7. Interrupt check
            if self._is_interrupt(command):
                log.info(f"Interrupt detected: '{command}'")
                tts_module.stop_speaking()
                self._ensure_mic_on()
                continue
            
            # 8. Final normalization
            final = self._modify_query(command)
            log.listen(f"Heard: {final}")
            return final
    
    def shutdown(self):
        """Cleanup."""
        try:
            self._ensure_mic_off()
            if self.driver:
                self.driver.quit()
        except Exception:
            pass

# -- Singleton -----------------------------------------------
stt = STT()

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- SpeechToText Test ---\n")
    print(f"Wake word: '{WAKE_WORD}'")
    print("Initializing Chrome STT...")
    
    try:
        stt.initialize()
    except Exception as e:
        print(f"\n[ERR] Init failed: {e}")
        print("[INFO] Make sure Chrome is installed & mic permission granted.\n")
        raise SystemExit(1)
    
    print("\n[READY] Say 'Jarvis <command>' - e.g. 'Jarvis hello'")
    print("Ctrl+C to stop.\n")
    
    try:
        while True:
            cmd = stt.listen()
            if cmd:
                print(f"\n  -> COMMAND: {cmd}\n")
    except KeyboardInterrupt:
        print("\n[STOP] Cleaning up...")
        stt.shutdown()
        print("[OK] SpeechToText test complete\n")