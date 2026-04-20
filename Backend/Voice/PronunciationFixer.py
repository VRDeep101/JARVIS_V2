# =============================================================
#  Backend/Voice/PronunciationFixer.py - Hindi -> English Filter
#
#  Kya karta:
#    - Hindi/Hinglish words jo Brian voice galat pronounce karta,
#      unko English equivalents se replace karta
#    - Common patterns fix karta (ik -> 'i k', tech abbrevs, etc)
#    - URLs, numbers, emojis clean karta
#    - Markdown strip karta (headers, bold, code blocks)
#    - TTS-safe final output deta
#
#  Main problem solve: Brian voice "accha" ko "uh-kah" bolta,
#  "theek" ko "thee-kay" - unnatural. Ye sab fix.
#
#  Usage:
#    from Backend.Voice.PronunciationFixer import fix_for_tts
#    clean = fix_for_tts("Accha Sir, theek hai, I'll do it")
#    -> "Alright Sir, okay, I'll do it"
# =============================================================

import re
from typing import Dict

from Backend.Utils.Logger import get_logger

log = get_logger("Pronunciation")

# =============================================================
#  1. HINDI/HINGLISH WORD REPLACEMENTS
#  Case-insensitive, whole-word match
# =============================================================
HINDI_REPLACEMENTS: Dict[str, str] = {
    # Affirmatives / Negatives
    "accha":     "alright",
    "acha":      "alright",
    "achha":     "alright",
    "theek":     "okay",
    "thik":      "okay",
    "theekh":    "okay",
    "haan":      "yes",
    "haanji":    "yes",
    "jee":       "yes",
    "nahi":      "no",
    "nahin":     "no",
    "nai":       "no",
    "bilkul":    "absolutely",
    "zaroor":    "certainly",
    
    # Fillers / Interjections (REMOVE)
    "bhai":      "",
    "yaar":      "",
    "arre":      "",
    "arey":      "",
    "oye":       "",
    "uff":       "",
    "haila":     "",
    "abey":      "",
    "ji":        "",
    "na":        "",
    
    # Action words
    "karo":      "do",
    "kar":       "do",
    "karenge":   "will do",
    "karna":     "do",
    "karunga":   "will do",
    "karungi":   "will do",
    "karta":     "does",
    "karti":     "does",
    "karein":    "do",
    "dekh":      "look",
    "dekho":     "look",
    "suno":      "listen",
    "sun":       "listen",
    "bata":      "tell",
    "batao":     "tell",
    "chal":      "come on",
    "chalo":     "come on",
    "chalega":   "okay",
    "ruko":      "wait",
    "ruk":       "wait",
    "jao":       "go",
    "ja":        "go",
    "aao":       "come",
    "aa":        "come",
    
    # Question words
    "kya":       "what",
    "kyu":       "why",
    "kyun":      "why",
    "kyunki":    "because",
    "kaise":     "how",
    "kahan":     "where",
    "kab":       "when",
    "kaun":      "who",
    "kitna":     "how much",
    "kitne":     "how many",
    
    # Pronouns
    "main":      "I",
    "mein":      "in",
    "mere":      "my",
    "mera":      "my",
    "meri":      "my",
    "mujhe":     "me",
    "tum":       "you",
    "tumhara":   "your",
    "tumhari":   "your",
    "aap":       "you",
    "aapka":     "your",
    "aapki":     "your",
    "uska":      "his",
    "uski":      "her",
    "woh":       "that",
    "yeh":       "this",
    "iska":      "its",
    
    # Be verbs
    "hai":       "is",
    "hain":      "are",
    "tha":       "was",
    "thi":       "was",
    "the":       "were",
    "hoga":      "will be",
    "hogi":      "will be",
    "ho":        "be",
    "hona":      "should be",
    
    # Time words
    "abhi":      "now",
    "phir":      "then",
    "pehle":     "first",
    "baad":      "after",
    "jaldi":     "quickly",
    "dheere":    "slowly",
    
    # Common combos
    "matlab":    "meaning",
    "lekin":     "but",
    "par":       "but",
    "aur":       "and",
    "ya":        "or",
    "toh":       "so",
    "sirf":      "only",
    "bas":       "just",
    "bhi":       "also",
    "sab":       "all",
    "kuch":      "something",
    "koi":       "someone",
    
    # Adjectives
    "bada":      "big",
    "chota":     "small",
    "accha":     "good",
    "bura":      "bad",
    "naya":      "new",
    "purana":    "old",
    
    # Emotional expressions
    "wah":       "wow",
    "wow":       "wow",
    "shabash":   "well done",
    "kamaal":    "amazing",
}

# =============================================================
#  2. TECH / ABBREVIATION EXPANSIONS
#  (Brian voice says "ai" as "eye" - fix to "A I")
# =============================================================
TECH_EXPANSIONS: Dict[str, str] = {
    # AI abbrevs - spaced so it reads letter by letter
    r"\bAI\b":    "A.I.",
    r"\bAGI\b":   "A.G.I.",
    r"\bML\b":    "M.L.",
    r"\bNLP\b":   "N.L.P.",
    r"\bLLM\b":   "L.L.M.",
    r"\bGPT\b":   "G.P.T.",
    r"\bAPI\b":   "A.P.I.",
    r"\bURL\b":   "U.R.L.",
    r"\bHTML\b":  "H.T.M.L.",
    r"\bCSS\b":   "C.S.S.",
    r"\bSQL\b":   "S.Q.L.",
    r"\bCPU\b":   "C.P.U.",
    r"\bGPU\b":   "G.P.U.",
    r"\bRAM\b":   "ram",  # reads fine as word
    r"\bSSD\b":   "S.S.D.",
    r"\bUSB\b":   "U.S.B.",
    r"\bHDMI\b":  "H.D.M.I.",
    r"\bOS\b":    "O.S.",
    r"\bPC\b":    "P.C.",
    r"\bTV\b":    "T.V.",
    r"\bIT\b":    "I.T.",   # when standalone
    r"\bPDF\b":   "P.D.F.",
    r"\bRTX\b":   "R.T.X.",
    r"\bFPS\b":   "F.P.S.",
    r"\bIP\b":    "I.P.",
    r"\bVPN\b":   "V.P.N.",
    r"\bUI\b":    "U.I.",
    r"\bUX\b":    "U.X.",
    r"\bIDE\b":   "I.D.E.",
    r"\bSDK\b":   "S.D.K.",
    r"\bCLI\b":   "C.L.I.",
    r"\bGUI\b":   "G.U.I.",
    
    # Brand-specific (pronounce right)
    r"\bChatGPT\b":  "Chat G.P.T.",
    r"\bOpenAI\b":   "Open A.I.",
    r"\bGemini\b":   "Gemini",
    r"\bClaude\b":   "Claude",
    r"\bYouTube\b":  "YouTube",
    r"\bWhatsApp\b": "WhatsApp",
}

# =============================================================
#  3. PUNCTUATION / FORMATTING CLEANUP
# =============================================================
def _remove_markdown(text: str) -> str:
    """Strip markdown formatting that confuses TTS."""
    # Bold / italic: **x**, *x*, __x__, _x_
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', text)
    
    # Code fences and inline code
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Headers
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    
    # Bullet points / numbered lists (keep content, drop marker)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Blockquote markers
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    
    # Horizontal rules
    text = re.sub(r'^[-=_]{3,}$', '', text, flags=re.MULTILINE)
    
    return text

def _strip_urls(text: str) -> str:
    """Remove URLs - they break TTS."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    return text

def _strip_emojis(text: str) -> str:
    """Remove emojis + most non-ASCII symbols (keep basic punctuation)."""
    # Emoji ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002500-\U00002BEF"  # chinese char
        "\U00002702-\U000027B0"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"
        "\u3030"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub('', text)

def _strip_internal_leaks(text: str) -> str:
    """Remove leaked internal thought lines from LLM."""
    prefixes = (
        "plan:", "risky:", "note:", "internal:",
        "thinking:", "reasoning:", "analysis:",
        "step 1:", "step 2:", "step 3:",
    )
    lines = []
    for line in text.split("\n"):
        if not any(line.lower().strip().startswith(p) for p in prefixes):
            lines.append(line)
    return "\n".join(lines)

def _fix_spacing(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)  # no space before punct
    text = re.sub(r'([.,!?;:])([a-zA-Z])', r'\1 \2', text)  # space after
    return text.strip()

# =============================================================
#  4. MAIN FIXER FUNCTION
# =============================================================
def fix_for_tts(text: str) -> str:
    """
    Main entry: clean text for TTS output.
    
    Order of operations:
    1. Strip markdown
    2. Remove URLs
    3. Remove emojis
    4. Remove internal leak lines
    5. Replace Hindi words
    6. Expand tech abbreviations
    7. Fix spacing
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Markdown
    text = _remove_markdown(text)
    
    # 2. URLs
    text = _strip_urls(text)
    
    # 3. Emojis
    text = _strip_emojis(text)
    
    # 4. Internal leaks
    text = _strip_internal_leaks(text)
    
    # 5. Hindi word replacements (case-insensitive, whole-word)
    for hindi, english in HINDI_REPLACEMENTS.items():
        pattern = r'\b' + re.escape(hindi) + r'\b'
        text = re.sub(pattern, english, text, flags=re.IGNORECASE)
    
    # 6. Tech expansions
    for pattern, replacement in TECH_EXPANSIONS.items():
        text = re.sub(pattern, replacement, text)
    
    # 7. Fix spacing & punctuation
    text = _fix_spacing(text)
    
    return text

# =============================================================
#  5. STT-SIDE HELPERS (for fuzzy correction)
# =============================================================

# Common STT misrecognitions - "jarvis" misheard as these
JARVIS_MISHEARD = {
    "harvis", "jarwis", "jarvish", "garvis", "java",
    "harvest", "travis", "harris", "carvis", "davies",
    "service", "jarvis's", "dervis", "darvis", "charvis",
    "jervis", "jarvez", "jerwis",
}

# Broader STT auto-corrections
STT_CORRECTIONS: Dict[str, str] = {
    # Jarvis variations
    "harvis": "jarvis", "jarwis": "jarvis", "jarvish": "jarvis",
    "garvis": "jarvis", "harvest": "jarvis", "travis": "jarvis",
    "harris": "jarvis", "carvis": "jarvis", "davies": "jarvis",
    "service": "jarvis", "dervis": "jarvis", "darvis": "jarvis",
    "charvis": "jarvis", "jervis": "jarvis",
    
    # Common app mishears
    "rome": "chrome", "chromium": "chrome",
    "vs codes": "vs code", "v.s. code": "vs code",
    "whats app": "whatsapp", "what's app": "whatsapp",
    "you tube": "youtube", "yt": "youtube",
    "spotifi": "spotify", "espotify": "spotify",
    
    # Number + word confusions
    "to do": "to-do", "1406": "1406", "fourteen o six": "1406",
    "fourteen six": "1406", "one four zero six": "1406",
    
    # Common Deep-related
    "deep la": "deep", "deep ji": "deep",
    "risky": "risky", "risk": "risky",
    "vishaka": "vishakha", "bishakha": "vishakha", "vishaaka": "vishakha",
    "naveen": "naveen", "naween": "naveen", "nawin": "naveen",
}

def correct_stt_text(text: str) -> tuple:
    """
    Fix common STT misrecognitions.
    Returns (corrected_text, was_changed).
    """
    if not text:
        return text, False
    
    words = text.split()
    corrected = []
    changed = False
    
    for word in words:
        # Normalize: lowercase, strip punctuation
        raw = word.lower().strip(".,!?;:\"'")
        
        if raw in STT_CORRECTIONS:
            replacement = STT_CORRECTIONS[raw]
            # Preserve capitalization of original if it was capitalized
            if word and word[0].isupper():
                replacement = replacement.capitalize()
            corrected.append(replacement)
            changed = True
        else:
            corrected.append(word)
    
    result = " ".join(corrected)
    return result, changed

def fuzzy_match_jarvis(text: str) -> bool:
    """True if any word in text might be a jarvis mishearing."""
    if not text:
        return False
    words = text.lower().split()
    for w in words:
        clean = w.strip(".,!?;:\"'")
        if clean == "jarvis" or clean in JARVIS_MISHEARD:
            return True
    return False

# =============================================================
#  TEST BLOCK
# =============================================================
if __name__ == "__main__":
    print("\n--- PronunciationFixer Test ---\n")
    
    # TTS fixes
    print("-- TTS Cleanup --\n")
    test_tts = [
        "Accha Sir, theek hai, I'll do it.",
        "Haan bhai, let me check the AI system.",
        "Arre yaar, the GPU temp is rising!",
        "**Important** note: GPT-4 API is rate limited.",
        "Check out https://example.com for docs.",
        "# Header\nAlright Sir, here's the plan.",
        "Plan: do X first.\nActually let's do Y.",
        "Sir, kya aap ready hain? 😊 Let's go!",
        "- bullet one\n- bullet two\nAlso, the URL is malformed.",
        "Matlab ye chij accha hai, theek hai na?",
    ]
    
    for t in test_tts:
        fixed = fix_for_tts(t)
        print(f"  IN : {t[:60]}")
        print(f"  OUT: {fixed[:60]}")
        print()
    
    # STT corrections
    print("\n-- STT Corrections --\n")
    test_stt = [
        "harvis open chrome",
        "jarwis play shape of you",
        "service turn on lights",
        "open rome browser",
        "call bishakha on whatsapp",
        "naween is coming over",
        "fourteen o six",
        "hello jarvis good morning",  # no change
    ]
    
    for t in test_stt:
        corrected, changed = correct_stt_text(t)
        tag = "[FIXED]" if changed else "[OK]   "
        print(f"  {tag} IN : {t}")
        print(f"          OUT: {corrected}")
        print()
    
    # Fuzzy jarvis
    print("\n-- Fuzzy Jarvis Detection --\n")
    fuzzy_tests = [
        "hey jarvis", "yo harvis", "listen davies",
        "hello world", "open chrome", "travis what time is it",
    ]
    for t in fuzzy_tests:
        detected = fuzzy_match_jarvis(t)
        print(f"  '{t[:30]:<30}' -> jarvis detected: {detected}")
    
    print("\n[OK] PronunciationFixer test complete\n")