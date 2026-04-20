# =============================================================
#  Frontend/Sounds/SoundManager.py - Sound Effects
#
#  Kya karta:
#    - Plays .wav sound effects (boot, mode change, notification, done)
#    - Auto-generates placeholder tones if .wav files missing
#    - Volume control
#    - Graceful if audio deps missing
#
#  Sound files go in Frontend/Sounds/files/:
#    - boot.wav
#    - mode_switch.wav
#    - notification.wav
#    - task_complete.wav
#    - error.wav
#
#  If files not present, plays generated tones.
# =============================================================

import os
import threading
import wave
import struct
import math
from pathlib import Path
from typing import Optional

from Backend.Utils.Logger import get_logger
from Backend.Utils.PathResolver import paths

log = get_logger("Sounds")

# -- Playback deps --------------------------------------------
try:
    import winsound
    WINSOUND_OK = True
except ImportError:
    WINSOUND_OK = False

try:
    import pygame
    pygame.mixer.init()
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

# =============================================================
#  Paths
# =============================================================
SOUNDS_DIR = paths.ROOT / "Frontend" / "Sounds" / "files"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

SOUND_FILES = {
    "boot":          SOUNDS_DIR / "boot.wav",
    "mode_switch":   SOUNDS_DIR / "mode_switch.wav",
    "notification":  SOUNDS_DIR / "notification.wav",
    "task_complete": SOUNDS_DIR / "task_complete.wav",
    "error":         SOUNDS_DIR / "error.wav",
}

# =============================================================
#  Placeholder tone generator
# =============================================================
def _generate_tone(filepath: Path, freq: float, duration: float,
                   volume: float = 0.3, sample_rate: int = 22050):
    """Generate a simple sine wave .wav file."""
    try:
        num_samples = int(sample_rate * duration)
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            # Envelope (fade in/out)
            env = min(1.0, t * 10, (duration - t) * 10)
            value = int(32767 * volume * env * math.sin(2 * math.pi * freq * t))
            samples.append(value)
        
        with wave.open(str(filepath), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for s in samples:
                wav.writeframesraw(struct.pack("<h", s))
        log.debug(f"Generated sound: {filepath.name}")
    except Exception as e:
        log.error(f"Tone gen error: {e}")


def _generate_chord(filepath: Path, freqs: list, duration: float,
                    volume: float = 0.2, sample_rate: int = 22050):
    """Generate a chord (multiple frequencies)."""
    try:
        num_samples = int(sample_rate * duration)
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            env = min(1.0, t * 10, (duration - t) * 8)
            combined = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
            value = int(32767 * volume * env * combined)
            samples.append(value)
        
        with wave.open(str(filepath), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for s in samples:
                wav.writeframesraw(struct.pack("<h", s))
    except Exception as e:
        log.error(f"Chord gen error: {e}")


# =============================================================
#  Auto-generate missing sound files on first run
# =============================================================
def _ensure_sound_files():
    """Generate placeholder sounds if .wav files don't exist."""
    configs = {
        "boot":          ("chord", [440, 660, 880], 1.2),
        "mode_switch":   ("chord", [523, 784], 0.3),
        "notification":  ("chord", [880, 1100], 0.25),
        "task_complete": ("chord", [523, 660, 880], 0.4),
        "error":         ("tone", 220, 0.4),
    }
    
    for name, filepath in SOUND_FILES.items():
        if filepath.exists():
            continue
        
        cfg = configs.get(name)
        if not cfg:
            continue
        
        if cfg[0] == "tone":
            _generate_tone(filepath, cfg[1], cfg[2])
        elif cfg[0] == "chord":
            _generate_chord(filepath, cfg[1], cfg[2])

_ensure_sound_files()


# =============================================================
#  SoundManager class
# =============================================================
class SoundManager:
    def __init__(self):
        self.volume = 0.5
        self.enabled = True
    
    def play(self, name: str, blocking: bool = False):
        """Play a sound effect by name."""
        if not self.enabled:
            return
        
        filepath = SOUND_FILES.get(name)
        if not filepath or not filepath.exists():
            log.debug(f"Sound not found: {name}")
            return
        
        if blocking:
            self._play_impl(filepath)
        else:
            t = threading.Thread(target=self._play_impl,
                                 args=(filepath,), daemon=True)
            t.start()
    
    def _play_impl(self, filepath: Path):
        try:
            if PYGAME_OK:
                sound = pygame.mixer.Sound(str(filepath))
                sound.set_volume(self.volume)
                sound.play()
            elif WINSOUND_OK:
                winsound.PlaySound(str(filepath), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            log.debug(f"Sound play error: {e}")
    
    def set_volume(self, vol: float):
        self.volume = max(0.0, min(1.0, vol))
    
    def set_enabled(self, on: bool):
        self.enabled = on


# Singleton
sounds = SoundManager()


if __name__ == "__main__":
    import time
    print("\n--- SoundManager Test ---\n")
    
    print(f"pygame: {PYGAME_OK}")
    print(f"winsound: {WINSOUND_OK}")
    print(f"Sound files folder: {SOUNDS_DIR}")
    
    for name, fp in SOUND_FILES.items():
        print(f"  {name:15} : {'[OK]' if fp.exists() else '[MISSING]'}")
    
    # Uncomment to actually play:
    # for name in SOUND_FILES:
    #     print(f"Playing: {name}")
    #     sounds.play(name, blocking=False)
    #     time.sleep(1.5)
    
    print("\n[OK] SoundManager test complete\n")