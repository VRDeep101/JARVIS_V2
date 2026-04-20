# =============================================================
#  Backend/Voice/TextToSpeech.py - Voice Output with Fallback
#
#  PRIMARY   : edge-tts (Microsoft Neural - en-US-BrianNeural)
#  FALLBACK  : pyttsx3 (Windows SAPI - offline, always works)
#
#  Auto-switches to fallback if edge-tts fails 3x.
#  Resets to primary after 5 minutes.
# =============================================================

import asyncio
import os
import random
import tempfile
import threading
import time
import queue
from typing import Optional

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Voice.PronunciationFixer import fix_for_tts
from Backend.Core.ContextManager import context

log = get_logger("TTS")

# -- Dependencies ---------------------------------------------
try:
    import edge_tts
    EDGE_TTS_OK = True
except ImportError:
    EDGE_TTS_OK = False
    log.error("edge-tts not installed. Run: pip install edge-tts")

try:
    import pyttsx3
    PYTTSX3_OK = True
except ImportError:
    PYTTSX3_OK = False
    log.warn("pyttsx3 not installed — no offline fallback. Run: pip install pyttsx3")

try:
    import pygame
    pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=512)
    pygame.mixer.init()
    PYGAME_OK = True
except Exception as e:
    PYGAME_OK = False
    log.error(f"Pygame init failed: {e}")

try:
    import keyboard as _kb
    KEYBOARD_OK = True
except ImportError:
    KEYBOARD_OK = False

# -- Config ---------------------------------------------------
VOICE_ID       = "en-US-BrianNeural"
DEFAULT_RATE   = "+0%"
DEFAULT_PITCH  = "+0Hz"

# Fallback (pyttsx3) - male voice preferred
FALLBACK_RATE  = 175   # words per minute
FALLBACK_VOL   = 1.0

TEMP_DIR = paths.CACHE_DIR
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Failover
EDGE_FAIL_THRESHOLD = 3         # N consecutive fails -> switch to fallback
EDGE_RETRY_AFTER = 300          # seconds before retrying edge-tts

# -- Overflow lines -------------------------------------------
OVERFLOW_LINES = [
    "The rest is on screen, Sir.",
    "Check the display for the full response.",
    "I've put everything on the screen.",
    "Details are on your display, Sir.",
    "Full response is on screen for you.",
]

# -- Mood mappings --------------------------------------------
EMOTION_RATE = {
    "happy": "+10%", "excited": "+15%", "motivated": "+12%",
    "sad": "-12%", "tired": "-12%", "lonely": "-10%",
    "anxious": "-10%", "angry": "-5%", "love": "-5%",
    "grateful": "+3%", "proud": "+5%", "bored": "+5%",
    "neutral": "+0%",
}

EMOTION_PITCH = {
    "happy": "+4Hz", "excited": "+6Hz", "motivated": "+4Hz",
    "sad": "-3Hz", "tired": "-2Hz", "lonely": "-3Hz",
    "anxious": "-2Hz", "angry": "-2Hz", "love": "+2Hz",
    "grateful": "+1Hz", "proud": "+3Hz", "bored": "+1Hz",
    "neutral": "+0Hz",
}

# -- Global state ---------------------------------------------
class _TTSState:
    is_speaking: bool = False
    internal_audio_blocked: bool = True
    should_stop: bool = False
    
    # Failover tracking
    edge_consecutive_fails: int = 0
    edge_disabled_until: float = 0.0   # timestamp

# -- pyttsx3 engine (lazy init) -------------------------------
_pyttsx3_engine = None
_pyttsx3_lock = threading.Lock()

def _get_pyttsx3():
    """Lazy-init pyttsx3 engine. Returns engine or None."""
    global _pyttsx3_engine
    if not PYTTSX3_OK:
        return None
    
    with _pyttsx3_lock:
        if _pyttsx3_engine is None:
            try:
                # Windows COM must be initialized per-thread before pyttsx3.init()
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                except Exception:
                    pass  # Not on Windows or pythoncom not available
                engine = pyttsx3.init()
                # Prefer male voice
                voices = engine.getProperty("voices")
                for v in voices:
                    name = (v.name or "").lower()
                    if "david" in name or "mark" in name or "male" in name:
                        engine.setProperty("voice", v.id)
                        break
                engine.setProperty("rate", FALLBACK_RATE)
                engine.setProperty("volume", FALLBACK_VOL)
                _pyttsx3_engine = engine
                log.info("pyttsx3 fallback engine ready")
            except Exception as e:
                log.error(f"pyttsx3 init failed: {e}")
                return None
    
    return _pyttsx3_engine

# -- Internal helpers -----------------------------------------
def _split_sentences(text: str) -> list:
    import re
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 2]

async def _generate_audio_edge(text: str, rate: str, pitch: str, output_path: str) -> bool:
    """Generate MP3 via edge-tts."""
    try:
        communicate = edge_tts.Communicate(text=text, voice=VOICE_ID, rate=rate, pitch=pitch)
        await communicate.save(output_path)
        return True
    except Exception as e:
        log.debug(f"Edge-tts sentence error: {e}")
        return False

def _play_file(filepath: str) -> bool:
    if not PYGAME_OK:
        return False
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if _TTSState.should_stop:
                pygame.mixer.music.stop()
                break
            pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
        return True
    except Exception as e:
        log.error(f"Playback error: {e}")
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        return False

def _should_use_fallback() -> bool:
    """Decide if we should skip edge-tts and go straight to fallback."""
    if not EDGE_TTS_OK:
        return True
    if _TTSState.edge_disabled_until > time.time():
        return True
    return False

def _mark_edge_fail():
    """Record an edge-tts failure. After threshold, disable for a while."""
    _TTSState.edge_consecutive_fails += 1
    if _TTSState.edge_consecutive_fails >= EDGE_FAIL_THRESHOLD:
        _TTSState.edge_disabled_until = time.time() + EDGE_RETRY_AFTER
        log.warn(
            f"edge-tts disabled for {EDGE_RETRY_AFTER}s (too many failures). "
            f"Using pyttsx3 fallback."
        )

def _mark_edge_success():
    _TTSState.edge_consecutive_fails = 0
    _TTSState.edge_disabled_until = 0.0

def _toggle_internal_audio():
    _TTSState.internal_audio_blocked = not _TTSState.internal_audio_blocked
    state = "BLOCKED" if _TTSState.internal_audio_blocked else "UNBLOCKED"
    log.info(f"Internal audio: {state}")

if KEYBOARD_OK:
    try:
        _kb.add_hotkey("windows+shift", _toggle_internal_audio)
    except Exception:
        pass

# =============================================================
#  Fallback speaker (pyttsx3)
# =============================================================
def _speak_fallback(text: str, rate_percent: str) -> bool:
    """
    Speak using pyttsx3 (offline, always available on Windows).
    rate_percent: e.g. "+10%" -> converted to WPM offset
    """
    engine = _get_pyttsx3()
    if engine is None:
        log.warn(f"[No TTS] {text}")
        return False
    
    # Convert rate percent to WPM
    try:
        pct = int(rate_percent.replace("%", "").replace("+", ""))
        wpm = max(80, min(280, FALLBACK_RATE + int(FALLBACK_RATE * pct / 100)))
    except Exception:
        wpm = FALLBACK_RATE
    
    try:
        with _pyttsx3_lock:
            engine.setProperty("rate", wpm)
            engine.say(text)
            engine.runAndWait()
        return True
    except Exception as e:
        log.error(f"pyttsx3 speak error: {e}")
        try:
            engine.stop()
        except Exception:
            pass
        return False

# =============================================================
#  TTS class
# =============================================================
class TTS:
    """Main TTS interface with auto-fallback."""
    
    @property
    def is_speaking(self) -> bool:
        return _TTSState.is_speaking
    
    def stop(self):
        _TTSState.should_stop = True
        # Also stop pyttsx3
        if _pyttsx3_engine:
            try:
                _pyttsx3_engine.stop()
            except Exception:
                pass
    
    # -- Primary path: edge-tts pipelined --------------------
    def _speak_edge(self, text: str, rate: str, pitch: str) -> bool:
        """Pipelined edge-tts. Returns False if ALL sentences fail."""
        cleaned = fix_for_tts(text)
        if not cleaned:
            return False
        
        sentences = _split_sentences(cleaned)
        if not sentences:
            return False
        
        audio_q = queue.Queue(maxsize=4)
        DONE = object()
        tmp_files = []
        file_lock = threading.Lock()
        any_success = [False]  # mutable flag for producer
        
        def producer():
            for i, sentence in enumerate(sentences):
                if _TTSState.should_stop:
                    break
                try:
                    tmp_fd, tmp_path = tempfile.mkstemp(
                        suffix=".mp3", dir=str(TEMP_DIR), prefix=f"tts_{i}_"
                    )
                    os.close(tmp_fd)
                    with file_lock:
                        tmp_files.append(tmp_path)
                    
                    loop = asyncio.new_event_loop()
                    ok = loop.run_until_complete(
                        _generate_audio_edge(sentence, rate, pitch, tmp_path)
                    )
                    loop.close()
                    
                    if ok and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                        audio_q.put(tmp_path)
                        any_success[0] = True
                    else:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                except Exception as e:
                    log.debug(f"Producer sentence {i}: {e}")
            
            audio_q.put(DONE)
        
        producer_thread = threading.Thread(target=producer, daemon=True, name="TTSProducer")
        producer_thread.start()
        
        try:
            while True:
                if _TTSState.should_stop:
                    break
                try:
                    item = audio_q.get(timeout=30)
                except queue.Empty:
                    break
                if item is DONE:
                    break
                _play_file(item)
                time.sleep(0.03)
        except Exception as e:
            log.error(f"Edge speak playback error: {e}")
        finally:
            try:
                if PYGAME_OK:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
            except Exception:
                pass
            
            producer_thread.join(timeout=3)
            
            with file_lock:
                for fpath in tmp_files:
                    try:
                        if os.path.exists(fpath):
                            os.remove(fpath)
                    except Exception:
                        pass
        
        return any_success[0]
    
    # -- Core speak: try edge, fall back to pyttsx3 ----------
    def _speak_raw(self, text: str, rate: str, pitch: str) -> bool:
        cleaned = fix_for_tts(text)
        if not cleaned:
            return False
        
        # Set flag
        _TTSState.is_speaking = True
        _TTSState.should_stop = False
        context.register_tts(cleaned)
        
        success = False
        try:
            # Try edge-tts first (if not disabled)
            if not _should_use_fallback():
                success = self._speak_edge(cleaned, rate, pitch)
                if success:
                    _mark_edge_success()
                else:
                    log.warn("edge-tts failed, using fallback")
                    _mark_edge_fail()
            
            # Fallback if edge failed or disabled
            if not success:
                success = _speak_fallback(cleaned, rate)
        
        except Exception as e:
            log.error(f"Speak error: {e}")
        
        finally:
            threading.Timer(0.5, context.clear_tts_cache).start()
            _TTSState.is_speaking = False
            _TTSState.should_stop = False
        
        return success
    
    # -- Public API ------------------------------------------
    def say(self, text: str, emotion: str = "neutral",
            rate: Optional[str] = None, pitch: Optional[str] = None) -> None:
        """Speak with emotion-adjusted voice. Long text gets overflow line."""
        if not text or not text.strip():
            return
        
        final_rate = rate or EMOTION_RATE.get(emotion, DEFAULT_RATE)
        final_pitch = pitch or EMOTION_PITCH.get(emotion, DEFAULT_PITCH)
        
        cleaned = fix_for_tts(str(text))
        sentences = _split_sentences(cleaned)
        is_long = len(sentences) > 3 or len(text) >= 200
        
        if is_long:
            short = ". ".join(s.rstrip(".") for s in sentences[:2])
            short += ". " + random.choice(OVERFLOW_LINES)
            self._speak_raw(short, final_rate, final_pitch)
        else:
            self._speak_raw(text, final_rate, final_pitch)
    
    def say_async(self, text: str, **kw) -> threading.Thread:
        """Fire-and-forget."""
        t = threading.Thread(target=self.say, args=(text,), kwargs=kw, daemon=True)
        t.start()
        return t
    
    # -- Status ------------------------------------------------
    def status(self) -> dict:
        """Debug info on TTS state."""
        return {
            "edge_tts_ok": EDGE_TTS_OK,
            "pyttsx3_ok": PYTTSX3_OK,
            "pygame_ok": PYGAME_OK,
            "edge_disabled_until": _TTSState.edge_disabled_until,
            "edge_consecutive_fails": _TTSState.edge_consecutive_fails,
            "using_fallback": _should_use_fallback(),
            "is_speaking": _TTSState.is_speaking,
        }

# =============================================================
#  Singleton + exports
# =============================================================
tts = TTS()

def say(text: str, **kw):
    tts.say(text, **kw)

def is_speaking() -> bool:
    return tts.is_speaking

def stop_speaking():
    tts.stop()

# =============================================================

# =============================================================
#  Main.py compat: state callbacks + stop_all
# =============================================================
_tts_state_callbacks = []

def _register_state_callback(callback):
    """Register callback(speaking: bool) - called on TTS state change."""
    _tts_state_callbacks.append(callback)

def _fire_state_callbacks(speaking: bool):
    """Internal - fire all registered state callbacks."""
    for cb in list(_tts_state_callbacks):
        try:
            cb(speaking)
        except Exception:
            pass

def _stop_all_tts():
    """Main.py compat: stop all TTS playback."""
    try:
        # Try to halt any pygame mixer if active
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.stop()
        except Exception:
            pass
        # Reset state
        _TTSState.is_speaking = False
    except Exception:
        pass

# Attach to tts singleton
tts.register_state_callback = _register_state_callback
tts.stop_all = _stop_all_tts
tts._fire_state_callbacks = _fire_state_callbacks

#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- TextToSpeech Test (with Fallback) ---\n")
    
    print(f"edge-tts available : {EDGE_TTS_OK}")
    print(f"pyttsx3 available  : {PYTTSX3_OK}")
    print(f"pygame  available  : {PYGAME_OK}")
    print()
    
    test_lines = [
        ("Hello Sir, this is the neutral test.", "neutral"),
        ("Accha Sir, theek hai, I'll get that done.", "neutral"),
        ("I'm so happy we finally got this working!", "happy"),
        ("Sir, take it easy. No rush at all.", "tired"),
        ("Absolutely crushing it today, Sir!", "motivated"),
    ]
    
    for text, emotion in test_lines:
        print(f"[{emotion}] {text}")
        tts.say(text, emotion=emotion)
        time.sleep(0.3)
    
    print("\n-- Long text overflow test --")
    long_text = (
        "Sir, quantum computing uses qubits instead of classical bits. "
        "Qubits can exist in superposition, enabling massive parallel computation. "
        "This makes them ideal for factoring large primes, simulating molecules, "
        "and breaking certain cryptographic schemes. However, maintaining coherence "
        "at room temperature remains a major challenge."
    )
    tts.say(long_text, emotion="neutral")
    
    print("\n-- Final status --")
    for k, v in tts.status().items():
        print(f"  {k:25} : {v}")
    
    print("\n[OK] TextToSpeech test complete\n")