# =============================================================
#  Backend/Brain/PersonalDataExtractor.py - Save PersonalData
#
#  Feature: "Jarvis, save personal data"
#    1. Notepad opens (blank .txt in Data/Cache/)
#    2. User can TYPE freely (any language - Hindi/English/mix)
#    3. User can also SPEAK (STT writes to same file)
#    4. Save file (Ctrl+S) OR close notepad OR say "Jarvis done"
#    5. Jarvis reads the file contents
#    6. Sends to LLM for extraction:
#       - Names (special people)
#       - Dates (birthdays, anniversaries)
#       - Preferences
#       - Relationships
#       - Goals
#       - Emotional significance rating
#    7. Saves each fact to Memory with importance
#    8. Deletes the temp file (privacy)
#    9. Speaks back what was learned
#
#  Usage:
#    from Backend.Brain.PersonalDataExtractor import personal_extractor
#    result = personal_extractor.start_session(on_speak=tts_callback)
# =============================================================

import os
import subprocess
import threading
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Dict, List

from dotenv import dotenv_values

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths
from Backend.Brain.Memory import memory
from Backend.Core.ErrorHandler import handle_error

log = get_logger("PersonalData")

env = dotenv_values(".env")
GROQ_KEY = env.get("GroqAPIKey", "").strip()
GROQ_MODEL = "llama-3.3-70b-versatile"

# -- Temp path -----------------------------------------------
TEMP_DIR = paths.DATA_DIR / "Cache"
TEMP_DIR.mkdir(exist_ok=True)

# -- Groq client (lazy) --------------------------------------
_groq_client = None

def _get_groq():
    global _groq_client
    if _groq_client is None and GROQ_KEY:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=GROQ_KEY)
        except Exception as e:
            log.error(f"Groq init failed: {e}")
    return _groq_client

# -- Extraction prompt ---------------------------------------
EXTRACTION_PROMPT = """You are analyzing personal data that a user wrote about themselves. Extract structured facts.

Rules:
- The text may be in English, Hindi, Hinglish, or mix. Understand all.
- Extract each distinct fact as a separate item.
- For each fact, assign:
  - type: "person" | "preference" | "goal" | "date" | "fact" | "relation" | "dislike" | "like"
  - content: the fact text (rewrite in clean English)
  - importance: 1-10 (10 = life-critical, 1 = casual)
  - category: short tag (family/friend/crush/work/hobby/etc)

Return ONLY valid JSON array, no other text:
[
  {"type": "person", "content": "Vishakha is someone very special to Sir", "importance": 10, "category": "crush", "name": "Vishakha", "attributes": {"likes": "pink roses", "birthday": "August 15"}},
  {"type": "goal", "content": "Build AGI by December 2026", "importance": 10, "category": "long_term"},
  {"type": "preference", "content": "Play Arijit Singh songs when sad", "importance": 7, "category": "mood_trigger"}
]

Only extract what's clearly stated. Don't invent."""

class PersonalDataExtractor:
    """Notepad-based personal data extraction."""
    
    def __init__(self):
        self.active_session = False
        self.current_file: Optional[Path] = None
        self._listen_callback: Optional[Callable] = None
    
    def start_session(
        self,
        on_speak: Callable[[str], None] = None,
        allow_voice_input: bool = True,
        voice_listen_fn: Optional[Callable[[], str]] = None,
    ) -> Dict:
        """
        Start a personal data capture session.
        
        Args:
            on_speak: callback to speak messages to user
            allow_voice_input: if True, also listen for speech
            voice_listen_fn: function that returns spoken text (blocking call)
        
        Returns dict with extraction results.
        """
        if self.active_session:
            return {"ok": False, "error": "Session already active"}
        
        speak = on_speak or (lambda msg: print(f"[Jarvis] {msg}"))
        
        # -- Create temp file ----------------------------
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_file = TEMP_DIR / f"personal_data_{timestamp}.txt"
        
        # Initial content with instructions
        initial_text = (
            "=== Jarvis Personal Data Capture ===\n"
            "Write anything you want me to remember.\n"
            "Any language is fine. You can also SPEAK and I'll write it here.\n"
            "Save and close this file when done (or say 'Jarvis done').\n"
            "----------------------------------------\n"
            "\n\n"
        )
        
        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(initial_text)
        except Exception as e:
            log.error(f"File create error: {e}")
            return {"ok": False, "error": str(e)}
        
        self.active_session = True
        log.info(f"Session started: {self.current_file.name}")
        
        # -- Announce ------------------------------------
        speak("Opening notepad, Sir. Write freely. Any language works.")
        
        # -- Open notepad --------------------------------
        notepad_path = paths.find_app("notepad") or "notepad.exe"
        try:
            notepad_process = subprocess.Popen(
                [notepad_path, str(self.current_file)]
            )
        except Exception as e:
            self.active_session = False
            return {"ok": False, "error": f"Could not open notepad: {e}"}
        
        # -- Start voice listener thread (if enabled) ----
        voice_thread = None
        stop_voice = threading.Event()
        
        if allow_voice_input and voice_listen_fn:
            def _voice_listen_loop():
                while not stop_voice.is_set():
                    try:
                        spoken = voice_listen_fn()  # blocking
                        if spoken and spoken.strip():
                            # Check for "done" command
                            if any(p in spoken.lower() for p in ["jarvis done", "finished",
                                                                  "i'm done", "that's all",
                                                                  "save it"]):
                                stop_voice.set()
                                return
                            # Append to file
                            try:
                                with open(self.current_file, "a", encoding="utf-8") as f:
                                    f.write(f"{spoken}\n")
                            except Exception:
                                pass
                    except Exception as e:
                        log.debug(f"Voice listen iteration error: {e}")
                        time.sleep(0.5)
            
            voice_thread = threading.Thread(target=_voice_listen_loop,
                                            daemon=True, name="PersonalVoiceListen")
            voice_thread.start()
        
        # -- Wait for notepad to close -------------------
        try:
            notepad_process.wait()  # blocks until user closes notepad
        except Exception:
            pass
        
        stop_voice.set()
        if voice_thread:
            voice_thread.join(timeout=1)
        
        # -- Read the file -------------------------------
        speak("Analyzing what you shared, Sir. One moment.")
        content = ""
        try:
            with open(self.current_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            log.error(f"Read error: {e}")
            self.active_session = False
            return {"ok": False, "error": "Could not read file"}
        
        # Strip initial instructions
        if "----------------------------------------" in content:
            content = content.split("----------------------------------------", 1)[1]
        content = content.strip()
        
        if not content or len(content) < 10:
            speak("Sir, the file was empty. No new memories saved.")
            self._cleanup_file()
            self.active_session = False
            return {"ok": True, "items_saved": 0, "empty": True}
        
        # -- Extract via LLM -----------------------------
        items = self._extract_with_llm(content)
        
        # -- Save to Memory ------------------------------
        saved_count = self._save_to_memory(items)
        
        # -- Cleanup -------------------------------------
        self._cleanup_file()
        self.active_session = False
        
        # -- Summary response ----------------------------
        summary = self._build_summary(items, saved_count)
        speak(summary)
        
        return {
            "ok": True,
            "items_saved": saved_count,
            "items": items,
            "summary": summary,
        }
    
    def _extract_with_llm(self, content: str) -> List[Dict]:
        """Send to Groq, parse JSON array."""
        client = _get_groq()
        if not client:
            log.error("Groq client unavailable")
            return []
        
        try:
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": f"Analyze this text:\n\n{content}"},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            raw = completion.choices[0].message.content.strip()
            
            # Strip markdown code fences if present
            raw = raw.replace("```json", "").replace("```", "").strip()
            
            # Find JSON array boundaries
            start = raw.find("[")
            end = raw.rfind("]")
            if start == -1 or end == -1:
                log.warn("No JSON array found in LLM response")
                return []
            
            items = json.loads(raw[start:end+1])
            if not isinstance(items, list):
                return []
            
            log.info(f"Extracted {len(items)} items from personal data")
            return items
        
        except Exception as e:
            log.error(f"Extraction error: {e}")
            return []
    
    def _save_to_memory(self, items: List[Dict]) -> int:
        """Save extracted items to memory."""
        saved = 0
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            try:
                item_type = item.get("type", "").lower()
                content = item.get("content", "").strip()
                importance = int(item.get("importance", 5))
                category = item.get("category", "general")
                
                if not content:
                    continue
                
                if item_type == "person":
                    name = item.get("name", "").strip()
                    if not name:
                        # Try to extract first capitalized word
                        import re
                        m = re.search(r"\b([A-Z][a-z]+)\b", content)
                        if m:
                            name = m.group(1)
                    
                    if name:
                        attributes = item.get("attributes", {})
                        if not isinstance(attributes, dict):
                            attributes = {}
                        memory.save_person(
                            name=name,
                            relation=category,
                            importance=importance,
                            notes=content,
                            attributes=attributes,
                        )
                        saved += 1
                
                elif item_type == "goal":
                    memory.save_goal(content, status="active", notes=category)
                    saved += 1
                
                elif item_type == "preference":
                    memory.save_fact(content, category=f"pref_{category}", confidence=max(3, importance // 2))
                    saved += 1
                
                elif item_type == "like":
                    memory.save_liked(content, confidence=max(2, importance // 2))
                    saved += 1
                
                elif item_type == "dislike":
                    memory.save_disliked(content, confidence=max(2, importance // 2))
                    saved += 1
                
                elif item_type == "date":
                    # Treat as high-value fact
                    memory.save_fact(content, category="important_date", confidence=8)
                    saved += 1
                
                elif item_type == "relation":
                    memory.save_fact(content, category="relationship", confidence=importance // 2)
                    saved += 1
                
                else:
                    # Generic fact
                    memory.save_fact(content, category=category,
                                     confidence=max(2, importance // 2))
                    saved += 1
            
            except Exception as e:
                log.error(f"Save item error: {e}")
                continue
        
        return saved
    
    def _build_summary(self, items: List[Dict], saved_count: int) -> str:
        """Human-friendly summary for voice feedback."""
        if saved_count == 0:
            return "Sir, I couldn't extract meaningful information. Try being more specific next time."
        
        # Group by type
        by_type: Dict[str, List] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("type", "fact")
            by_type.setdefault(t, []).append(item)
        
        parts = [f"Saved, Sir. I've learned {saved_count} new {'thing' if saved_count == 1 else 'things'} about you."]
        
        # Highlight top items
        highlights = []
        if "person" in by_type:
            names = [it.get("name", "someone") for it in by_type["person"][:2]]
            if names:
                highlights.append(f"{', '.join(names)}")
        if "goal" in by_type:
            highlights.append(f"{len(by_type['goal'])} goal{'s' if len(by_type['goal']) > 1 else ''}")
        if "date" in by_type:
            highlights.append(f"{len(by_type['date'])} important date{'s' if len(by_type['date']) > 1 else ''}")
        
        if highlights:
            parts.append(f"Including: {', '.join(highlights)}.")
        
        return " ".join(parts)
    
    def _cleanup_file(self):
        """Delete temp file for privacy."""
        if self.current_file and self.current_file.exists():
            try:
                self.current_file.unlink()
                log.info("Temp file deleted")
            except Exception as e:
                log.error(f"File delete error: {e}")
        self.current_file = None

# -- Singleton ------------------------------------------------
personal_extractor = PersonalDataExtractor()

# Alias + compat method for Main.py
personal_data_extractor = personal_extractor

def _trigger_compat(self, on_speak=None):
    """Main.py compat: trigger() -> start_session()."""
    return self.start_session(on_speak=on_speak)

PersonalDataExtractor.trigger = _trigger_compat

# -- Test block -----------------------------------------------
if __name__ == "__main__":
    print("\n--- PersonalDataExtractor Test ---\n")
    
    if not GROQ_KEY or GROQ_KEY == "paste_here":
        print("[WARN] GroqAPIKey not set - skipping LLM test")
        print("[INFO] Manual test: run this from Main.py flow\n")
    else:
        print("This test opens Notepad. Type something and close it.")
        print("Starting in 3 seconds...\n")
        time.sleep(3)
        
        def speak_cb(msg):
            print(f"[SPEAK] {msg}")
        
        result = personal_extractor.start_session(
            on_speak=speak_cb,
            allow_voice_input=False,  # skip voice in test
        )
        
        print(f"\n-- Result --")
        print(f"OK: {result.get('ok')}")
        print(f"Saved: {result.get('items_saved', 0)}")
        if result.get('items'):
            print(f"Items:")
            for item in result['items'][:5]:
                print(f"  {item}")
    
    print("\n[OK] PersonalDataExtractor test complete\n")