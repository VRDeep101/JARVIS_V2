# =============================================================
#  Backend/External/ImageGenerator.py - Continuous Streaming
#
#  CONTINUOUS GENERATION LOGIC:
#    - User: "generate image of sunset"
#    - Jarvis: starts generating 4 images in parallel
#    - Display image #1 as soon as ready -> speak "Here's first one, Sir"
#    - Keep generating 4 MORE in background (pipeline full)
#    - User: "next" -> display #2
#    - User: "change to cyberpunk" -> cancel current, restart
#    - User: "stop" / "close" -> terminate pipeline
#
#  Uses HuggingFace FLUX.1-schnell (free)
#  Queue-based: always 4 ready + 4 generating
#
#  Usage:
#    from Backend.External.ImageGenerator import image_gen
#    image_gen.start("sunset", on_ready=callback, on_speak=tts)
#    image_gen.next()     # show next in queue
#    image_gen.change_prompt("cyberpunk city")
#    image_gen.stop()
# =============================================================

import asyncio
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from dotenv import dotenv_values

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths

log = get_logger("ImageGen")

env = dotenv_values(".env")
HF_KEY = env.get("HuggingFaceAPIKey", "").strip()

try:
    from huggingface_hub import InferenceClient
    HF_OK = True
except ImportError:
    HF_OK = False

_client = None

def _get_client():
    global _client
    if _client is None and HF_OK and HF_KEY:
        try:
            _client = InferenceClient(api_key=HF_KEY)
        except Exception as e:
            log.error(f"HF init: {e}")
    return _client

MODEL = "black-forest-labs/FLUX.1-schnell"
IMAGES_DIR = paths.IMAGES_DIR
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================
#  Image generation helpers
# =============================================================
def _clean_prompt(prompt: str) -> str:
    p = prompt.lower().strip()
    for prefix in ["generate image of", "generate images of", "create image of",
                   "generate image", "generate images", "create image"]:
        if p.startswith(prefix):
            p = p[len(prefix):].strip()
    return p.strip(" ,.-:")

def _generate_one(prompt: str, index: int, session_id: str) -> Optional[str]:
    """Generate single image. Returns filepath or None."""
    client = _get_client()
    if not client:
        return None
    
    try:
        image = client.text_to_image(
            prompt=f"{prompt}, ultra detailed, high quality, 4K, sharp focus",
            model=MODEL,
        )
        safe_name = _clean_prompt(prompt).replace(" ", "_")[:40]
        filename = f"{session_id}_{safe_name}_{index}.jpg"
        filepath = IMAGES_DIR / filename
        image.save(str(filepath))
        log.info(f"Image {index} ready: {filename}")
        return str(filepath)
    except Exception as e:
        log.error(f"Gen error image {index}: {e}")
        return None

def _open_image(filepath: str):
    """Open image in default viewer."""
    try:
        os.startfile(filepath)
    except Exception as e:
        log.error(f"Open image error: {e}")

# =============================================================
#  ImageGenerator class
# =============================================================
class ImageGenerator:
    """
    Continuous pipeline:
    - Maintains queue of ready images
    - Always generating N in background
    - User 'next' -> pop from queue, show, trigger new generation
    """
    
    BATCH_SIZE = 4       # generate 4 at a time
    QUEUE_TARGET = 4     # always aim for 4 ready
    
    def __init__(self):
        self.active = False
        self.current_prompt: Optional[str] = None
        self.session_id: str = ""
        
        self.ready_queue: "queue.Queue[str]" = queue.Queue()
        self.displayed_count = 0
        
        self._stop_event = threading.Event()
        self._producer_thread: Optional[threading.Thread] = None
        
        self.on_speak: Optional[Callable] = None
        self.on_ready: Optional[Callable] = None  # called with filepath
    
    # =========================================================
    #  START / STOP
    # =========================================================
    def start(
        self,
        prompt: str,
        on_ready: Optional[Callable[[str], None]] = None,
        on_speak: Optional[Callable[[str], None]] = None,
    ) -> Dict:
        """Start image generation session."""
        if not HF_OK:
            return {"ok": False, "message": "huggingface_hub not installed"}
        if not HF_KEY or HF_KEY == "paste_here":
            return {"ok": False, "message": "HuggingFace API key not set, Sir."}
        
        if self.active:
            self.stop()  # restart
        
        cleaned = _clean_prompt(prompt)
        if not cleaned:
            return {"ok": False, "message": "Need an image description, Sir."}
        
        self.current_prompt = cleaned
        self.session_id = datetime.now().strftime("%H%M%S")
        self.ready_queue = queue.Queue()
        self.displayed_count = 0
        self._stop_event.clear()
        self.on_speak = on_speak
        self.on_ready = on_ready
        self.active = True
        
        # Start producer thread
        self._producer_thread = threading.Thread(
            target=self._producer_loop,
            daemon=True,
            name="ImageProducer",
        )
        self._producer_thread.start()
        
        msg = f"Generating {cleaned}, Sir. First image coming up."
        if on_speak:
            on_speak(msg)
        
        return {
            "ok": True,
            "message": msg,
            "session_id": self.session_id,
        }
    
    def stop(self) -> Dict:
        """Stop pipeline, clean up."""
        self._stop_event.set()
        self.active = False
        
        if self._producer_thread and self._producer_thread.is_alive():
            self._producer_thread.join(timeout=3)
        
        # Clear queue
        while not self.ready_queue.empty():
            try:
                self.ready_queue.get_nowait()
            except queue.Empty:
                break
        
        msg = f"Stopped image generation, Sir. Showed {self.displayed_count} images."
        log.info(msg)
        return {"ok": True, "message": msg, "displayed": self.displayed_count}
    
    def change_prompt(self, new_prompt: str) -> Dict:
        """Switch to new prompt mid-session."""
        old = self.current_prompt
        self.stop()
        time.sleep(0.3)
        result = self.start(new_prompt, on_ready=self.on_ready, on_speak=self.on_speak)
        result["message"] = f"Switched from '{old}' to '{new_prompt}', Sir. Generating fresh images."
        return result
    
    # =========================================================
    #  NEXT / DISPLAY
    # =========================================================
    def next(self, wait_sec: int = 30) -> Dict:
        """
        Pop next image from queue and display.
        If queue empty, wait up to wait_sec for one.
        """
        if not self.active:
            return {"ok": False, "message": "No image session active, Sir."}
        
        try:
            filepath = self.ready_queue.get(timeout=wait_sec)
        except queue.Empty:
            return {"ok": False, "message": "Still generating, Sir. Give it a moment."}
        
        self.displayed_count += 1
        
        # Display
        _open_image(filepath)
        
        # Callback
        if self.on_ready:
            try:
                self.on_ready(filepath)
            except Exception as e:
                log.error(f"on_ready callback: {e}")
        
        num = self.displayed_count
        if num == 1:
            msg = "Here's the first one, Sir."
        elif num == 2:
            msg = "Second image up."
        elif num == 3:
            msg = "Third."
        else:
            msg = f"Image {num}."
        
        return {
            "ok": True,
            "filepath": filepath,
            "image_number": num,
            "message": msg,
        }
    
    # =========================================================
    #  PRODUCER LOOP (background)
    # =========================================================
    def _producer_loop(self):
        """Continuously generate images, maintain queue."""
        batch_num = 0
        while not self._stop_event.is_set():
            # Only generate if queue is below target
            if self.ready_queue.qsize() >= self.QUEUE_TARGET:
                time.sleep(0.5)
                continue
            
            # Generate BATCH_SIZE images in parallel
            batch_num += 1
            log.info(f"Generating batch {batch_num} (prompt: {self.current_prompt})")
            
            threads = []
            results = [None] * self.BATCH_SIZE
            
            def _gen_one_idx(idx):
                if self._stop_event.is_set():
                    return
                results[idx] = _generate_one(
                    self.current_prompt,
                    batch_num * 10 + idx,
                    self.session_id,
                )
            
            for i in range(self.BATCH_SIZE):
                if self._stop_event.is_set():
                    break
                t = threading.Thread(target=_gen_one_idx, args=(i,),
                                     daemon=True, name=f"Gen_{i}")
                t.start()
                threads.append(t)
            
            for t in threads:
                t.join(timeout=60)
            
            if self._stop_event.is_set():
                break
            
            # Enqueue successful results
            for path in results:
                if path:
                    self.ready_queue.put(path)
            
            # Brief pause before next batch if queue is full
            while (not self._stop_event.is_set() and
                   self.ready_queue.qsize() >= self.QUEUE_TARGET):
                time.sleep(1)
        
        log.info("Producer loop ended")
    
    def status(self) -> Dict:
        return {
            "active": self.active,
            "prompt": self.current_prompt,
            "queue_size": self.ready_queue.qsize() if self.active else 0,
            "displayed": self.displayed_count,
        }

# Singleton
image_gen = ImageGenerator()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- ImageGenerator Test ---\n")
    
    print(f"huggingface_hub: {HF_OK}")
    print(f"HF Key set: {bool(HF_KEY and HF_KEY != 'paste_here')}")
    
    # Non-destructive tests
    print("\n-- Prompt cleaning --")
    tests = [
        "generate image of sunset",
        "create image cyberpunk city",
        "sunset at the beach",
    ]
    for t in tests:
        print(f"  '{t}' -> '{_clean_prompt(t)}'")
    
    # Uncomment for live test (will hit HF API + generate actual images):
    # print("\n-- Live generation test --")
    # def on_speak(msg): print(f"  [SPEAK] {msg}")
    # def on_ready(path): print(f"  [READY] {path}")
    # 
    # r = image_gen.start("sunset over mountains", on_ready=on_ready, on_speak=on_speak)
    # print(f"  Start: {r}")
    # 
    # # Wait for first image
    # time.sleep(15)
    # r = image_gen.next()
    # print(f"  Next: {r.get('message')}")
    # 
    # time.sleep(3)
    # image_gen.stop()
    
    print("\n[OK] ImageGenerator test complete\n")