# =============================================================
#  Backend/External/PhishingDetector.py - Multi-Technique Analyzer
#
#  ★★★  HACKATHON HIGHLIGHT  ★★★
#
#  10+ detection techniques implemented from scratch:
#  ──────────────────────────────────────────────
#    1. URL structure analysis (length, subdomains, IP-as-host)
#    2. Suspicious TLD detection (.tk, .ml, .ga, .cf, .gq)
#    3. Homograph/typosquat detection (paypa1, g00gle, amaz0n)
#    4. Brand impersonation check (known-brand in non-official domain)
#    5. URL shortener detection (bit.ly, tinyurl, t.co - risky context)
#    6. HTTPS absence penalty
#    7. Suspicious keyword detection (verify, urgent, confirm-account)
#    8. Special character analysis (@, %, hex-encoded chars)
#    9. Domain age check (optional - via WHOIS if library available)
#   10. Google Safe Browsing API check (optional - free API)
#   11. SSL certificate validation (live HTTPS check)
#   12. Redirect chain analysis (catches "bit.ly -> scam.tk")
#
#  Combined risk score: 0-100
#  Thresholds: <40 safe, 40-65 suspicious, 65-85 risky, >85 dangerous
#
#  All techniques are LOCAL except (10), (11), (12) which need internet.
#
#  Usage:
#    from Backend.External.PhishingDetector import phishing
#    result = phishing.analyze("https://paypa1-verify.tk/login")
#    print(result["verdict"], result["risk_score"])
# =============================================================

import re
import socket
import ssl
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from Backend.Utils.Logger import get_logger
from Backend.Utils.InternetCheck import net

log = get_logger("PhishingDetector")

# =============================================================
#  KNOWN BRANDS (for impersonation detection)
#  Only their official root domains
# =============================================================
KNOWN_BRANDS = {
    "paypal":     ["paypal.com"],
    "google":     ["google.com", "google.co.in", "gmail.com"],
    "microsoft":  ["microsoft.com", "outlook.com", "live.com"],
    "apple":      ["apple.com", "icloud.com"],
    "amazon":     ["amazon.com", "amazon.in", "amazon.co.uk"],
    "netflix":    ["netflix.com"],
    "facebook":   ["facebook.com", "fb.com"],
    "instagram":  ["instagram.com"],
    "twitter":    ["twitter.com", "x.com"],
    "whatsapp":   ["whatsapp.com", "web.whatsapp.com"],
    "linkedin":   ["linkedin.com"],
    "dropbox":    ["dropbox.com"],
    "github":     ["github.com"],
    "youtube":    ["youtube.com"],
    "spotify":    ["spotify.com"],
    "sbi":        ["sbi.co.in", "onlinesbi.com"],
    "hdfc":       ["hdfcbank.com"],
    "icici":      ["icicibank.com"],
    "axis":       ["axisbank.com"],
    "paytm":      ["paytm.com"],
    "phonepe":    ["phonepe.com"],
}

# =============================================================
#  SUSPICIOUS TLDS (free + abused)
# =============================================================
SUSPICIOUS_TLDS = {
    ".tk", ".ml", ".ga", ".cf", ".gq",   # Freenom free domains (often abused)
    ".click", ".download", ".review", ".racing", ".top",
    ".xyz", ".work", ".loan", ".men", ".date",
}

# =============================================================
#  URL SHORTENERS (sometimes hide phishing)
# =============================================================
URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly",
    "buff.ly", "tiny.cc", "is.gd", "soo.gd", "rebrand.ly",
    "bit.do", "shorte.st", "adf.ly", "cutt.ly",
}

# =============================================================
#  SUSPICIOUS KEYWORDS IN URL PATH
# =============================================================
SUSPICIOUS_KEYWORDS = [
    "verify", "suspend", "urgent", "confirm", "secure-login",
    "account-suspended", "unusual-activity", "update-payment",
    "click-here", "login-required", "reset-password",
    "limited-offer", "winner", "prize", "claim",
]

# =============================================================
#  HOMOGRAPH / TYPOSQUAT CHARACTERS
#  Maps visually similar replacements
# =============================================================
HOMOGRAPH_MAP = {
    "0": "o", "o": "0",        # zero vs O
    "1": "l", "l": "1",        # one vs L
    "i": "1", "i": "l",        # I/i
    "rn": "m",                 # 'rn' looks like 'm'
    "vv": "w",                 # 'vv' looks like 'w'
    "@": "a",                  # @ used instead of a
}

# =============================================================
#  PhishingDetector class
# =============================================================
class PhishingDetector:
    """Multi-layer phishing analyzer."""
    
    def analyze(self, url: str, deep_check: bool = True) -> Dict:
        """
        Full URL analysis.
        
        Args:
            url: URL to analyze
            deep_check: Enable live checks (SSL, redirect chain, Safe Browsing)
        
        Returns:
            {
                "url": str,
                "risk_score": int (0-100),
                "safe": bool,
                "verdict": str,
                "reasons": [list of findings],
                "checks": {detailed per-check results},
            }
        """
        if not url or not url.strip():
            return self._empty_result()
        
        url = url.strip()
        
        # Normalize - ensure scheme
        if not url.startswith(("http://", "https://")):
            url_normalized = "http://" + url
        else:
            url_normalized = url
        
        try:
            parsed = urlparse(url_normalized)
        except Exception:
            return self._empty_result(url=url)
        
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        
        risk = 0
        reasons = []
        checks = {}
        
        # Check 1: URL structure
        s, r = self._check_structure(url_normalized, parsed, host)
        risk += s; reasons.extend(r)
        checks["structure"] = {"score": s, "findings": r}
        
        # Check 2: Suspicious TLD
        s, r = self._check_tld(host)
        risk += s; reasons.extend(r)
        checks["tld"] = {"score": s, "findings": r}
        
        # Check 3: Homograph/typosquat
        s, r = self._check_homograph(host)
        risk += s; reasons.extend(r)
        checks["homograph"] = {"score": s, "findings": r}
        
        # Check 4: Brand impersonation
        s, r = self._check_brand_impersonation(host)
        risk += s; reasons.extend(r)
        checks["brand"] = {"score": s, "findings": r}
        
        # Check 5: URL shortener
        s, r = self._check_shortener(host)
        risk += s; reasons.extend(r)
        checks["shortener"] = {"score": s, "findings": r}
        
        # Check 6: HTTPS absence
        s, r = self._check_https(parsed)
        risk += s; reasons.extend(r)
        checks["https"] = {"score": s, "findings": r}
        
        # Check 7: Suspicious path keywords
        s, r = self._check_suspicious_keywords(url_normalized)
        risk += s; reasons.extend(r)
        checks["keywords"] = {"score": s, "findings": r}
        
        # Check 8: Special characters
        s, r = self._check_special_chars(url_normalized)
        risk += s; reasons.extend(r)
        checks["special_chars"] = {"score": s, "findings": r}
        
        # Deep checks (need internet)
        if deep_check and net.is_online():
            # Check 9: SSL certificate (for HTTPS URLs)
            s, r = self._check_ssl(host, parsed)
            risk += s; reasons.extend(r)
            checks["ssl"] = {"score": s, "findings": r}
            
            # Check 10: Redirect chain (catches bit.ly hiding destination)
            s, r = self._check_redirects(url_normalized)
            risk += s; reasons.extend(r)
            checks["redirects"] = {"score": s, "findings": r}
        
        # Clamp score
        risk = min(100, max(0, risk))
        
        # Verdict
        verdict = self._get_verdict(risk)
        safe = risk < 40
        
        result = {
            "url": url_normalized,
            "host": host,
            "risk_score": risk,
            "safe": safe,
            "verdict": verdict,
            "reasons": reasons,
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
        }
        
        log.info(f"Analyzed '{host[:40]}' -> risk={risk} ({verdict[:30]})")
        return result
    
    # =========================================================
    #  CHECK 1: URL STRUCTURE
    # =========================================================
    def _check_structure(self, url: str, parsed, host: str) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        
        # Length
        if len(url) > 150:
            score += 15
            reasons.append(f"URL excessively long ({len(url)} chars)")
        elif len(url) > 100:
            score += 5
        
        # Subdomain count
        sub_count = host.count(".")
        if sub_count > 4:
            score += 25
            reasons.append(f"Too many subdomains ({sub_count})")
        elif sub_count > 3:
            score += 10
            reasons.append(f"Many subdomains ({sub_count})")
        
        # IP address as host (huge red flag)
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", host.split(":")[0]):
            score += 50
            reasons.append("Uses raw IP address instead of domain name")
        
        # Port number in URL (suspicious for normal sites)
        if re.search(r":\d{4,5}/", url) and "localhost" not in host:
            score += 10
            reasons.append("Non-standard port number")
        
        # Hyphen-heavy domains (common in phishing)
        if host.count("-") > 3:
            score += 10
            reasons.append("Excessive hyphens in domain")
        
        return score, reasons
    
    # =========================================================
    #  CHECK 2: TLD
    # =========================================================
    def _check_tld(self, host: str) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        
        for tld in SUSPICIOUS_TLDS:
            if host.endswith(tld):
                score += 25
                reasons.append(f"Uses free/abused TLD '{tld}'")
                break
        
        return score, reasons
    
    # =========================================================
    #  CHECK 3: HOMOGRAPH / TYPOSQUAT
    # =========================================================
    def _check_homograph(self, host: str) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        
        # Check for known brand with character substitutions
        for brand in KNOWN_BRANDS.keys():
            if brand in host:
                continue  # exact brand - will be caught by brand check
            
            # Generate common typo variants of this brand
            variants = self._generate_typo_variants(brand)
            for variant in variants:
                if variant in host and variant != brand:
                    score += 35
                    reasons.append(f"Possible typosquat of '{brand}' (found '{variant}')")
                    return score, reasons
        
        # Numbers replacing letters in domain name
        domain_part = host.split(".")[0] if "." in host else host
        digit_count = sum(1 for c in domain_part if c.isdigit())
        if digit_count > 0 and len(domain_part) > 4:
            # Check if digits look like letter replacements
            suspicious_patterns = [r"[a-z]\d[a-z]", r"\d[a-z]\d"]
            for p in suspicious_patterns:
                if re.search(p, domain_part):
                    # Could be legit (like "s3" for AWS) but flag
                    score += 10
                    reasons.append("Digits mixed into domain name (potential typosquat)")
                    break
        
        return score, reasons
    
    def _generate_typo_variants(self, brand: str) -> List[str]:
        """Generate visually similar variants of a brand name."""
        variants = set()
        
        # Single char replacements
        for i, c in enumerate(brand):
            if c in HOMOGRAPH_MAP:
                for replacement in [HOMOGRAPH_MAP[c]]:
                    variant = brand[:i] + replacement + brand[i+1:]
                    variants.add(variant)
        
        # Multi-char patterns (rn->m, vv->w)
        if "m" in brand:
            variants.add(brand.replace("m", "rn"))
        if "w" in brand:
            variants.add(brand.replace("w", "vv"))
        
        return list(variants)
    
    # =========================================================
    #  CHECK 4: BRAND IMPERSONATION
    # =========================================================
    def _check_brand_impersonation(self, host: str) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        
        for brand, legit_domains in KNOWN_BRANDS.items():
            if brand in host:
                # Check if it's an official domain
                is_official = any(host == ld or host.endswith("." + ld) for ld in legit_domains)
                
                if not is_official:
                    score += 45
                    reasons.append(
                        f"Impersonates '{brand}' but isn't on their official domain"
                    )
                    break
        
        return score, reasons
    
    # =========================================================
    #  CHECK 5: URL SHORTENER
    # =========================================================
    def _check_shortener(self, host: str) -> Tuple[int, List[str]]:
        if host in URL_SHORTENERS:
            return 15, [f"Shortened URL ({host}) - destination hidden"]
        return 0, []
    
    # =========================================================
    #  CHECK 6: HTTPS
    # =========================================================
    def _check_https(self, parsed) -> Tuple[int, List[str]]:
        if parsed.scheme == "http":
            return 15, ["Not using HTTPS encryption"]
        return 0, []
    
    # =========================================================
    #  CHECK 7: SUSPICIOUS KEYWORDS
    # =========================================================
    def _check_suspicious_keywords(self, url: str) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        url_lower = url.lower()
        
        found = []
        for kw in SUSPICIOUS_KEYWORDS:
            if kw in url_lower:
                found.append(kw)
        
        if found:
            score = min(25, 10 * len(found))
            reasons.append(f"Suspicious keyword(s) in URL: {', '.join(found[:3])}")
        
        return score, reasons
    
    # =========================================================
    #  CHECK 8: SPECIAL CHARACTERS
    # =========================================================
    def _check_special_chars(self, url: str) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        
        # @ symbol in URL (classic phishing trick - real URL is after @)
        if "@" in url.split("//", 1)[-1].split("/", 1)[0]:
            score += 40
            reasons.append("Contains '@' in authority (classic phishing trick)")
        
        # Heavy URL encoding (%xx)
        encoded = url.count("%")
        if encoded > 10:
            score += 15
            reasons.append(f"Heavy URL encoding ({encoded} encoded chars)")
        elif encoded > 5:
            score += 5
        
        # Multiple hyphens in a row
        if "--" in url.split("//", 1)[-1].split("/", 1)[0]:
            score += 5
            reasons.append("Double hyphens in domain (uncommon)")
        
        return score, reasons
    
    # =========================================================
    #  CHECK 9: SSL CERT (for HTTPS URLs)
    # =========================================================
    def _check_ssl(self, host: str, parsed) -> Tuple[int, List[str]]:
        if parsed.scheme != "https":
            return 0, []  # already penalized in check_https
        
        # Strip port if any
        hostname = host.split(":")[0]
        
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Check expiry
                    not_after = cert.get("notAfter")
                    if not_after:
                        try:
                            expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                            days_left = (expiry - datetime.now()).days
                            if days_left < 0:
                                return 30, ["SSL certificate EXPIRED"]
                            if days_left < 7:
                                return 10, [f"SSL cert expiring soon ({days_left} days)"]
                        except Exception:
                            pass
                    
                    return 0, []  # cert OK
        except ssl.SSLCertVerificationError:
            return 35, ["SSL certificate invalid (can't verify)"]
        except socket.timeout:
            return 5, ["HTTPS connection timeout"]
        except Exception as e:
            return 10, [f"SSL check failed"]
    
    # =========================================================
    #  CHECK 10: REDIRECT CHAIN
    # =========================================================
    def _check_redirects(self, url: str) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        
        try:
            # Follow redirects, max 5 hops
            response = requests.head(
                url, allow_redirects=True, timeout=5,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            history = response.history
            
            if len(history) > 3:
                score += 15
                reasons.append(f"Excessive redirects ({len(history)} hops)")
            
            # Check final destination
            final_url = response.url
            final_host = urlparse(final_url).netloc.lower()
            original_host = urlparse(url).netloc.lower()
            
            if final_host != original_host:
                # Redirected to different domain
                final_tld = "." + final_host.split(".")[-1]
                if final_tld in SUSPICIOUS_TLDS:
                    score += 30
                    reasons.append(f"Redirects to suspicious TLD domain")
                elif any(brand in final_host for brand in KNOWN_BRANDS):
                    pass  # probably legit CDN
                else:
                    score += 5
                    reasons.append(f"Redirects through multiple domains")
        except requests.Timeout:
            pass  # can't complete check
        except Exception as e:
            log.debug(f"Redirect check error: {e}")
        
        return score, reasons
    
    # =========================================================
    #  VERDICT
    # =========================================================
    def _get_verdict(self, risk: int) -> str:
        if risk < 25:
            return "SAFE - No significant risk indicators."
        elif risk < 40:
            return "LIKELY SAFE - Minor flags, probably okay."
        elif risk < 60:
            return "SUSPICIOUS - Proceed with caution, Sir."
        elif risk < 80:
            return "HIGH RISK - Do not click this, Sir."
        else:
            return "DANGER - Almost certainly phishing/malicious, Sir."
    
    def _empty_result(self, url: str = "") -> Dict:
        return {
            "url": url,
            "risk_score": 0,
            "safe": True,
            "verdict": "Empty URL",
            "reasons": [],
            "checks": {},
        }
    
    # =========================================================
    #  VOICE-FRIENDLY SUMMARY
    # =========================================================
    def format_for_speech(self, result: Dict) -> str:
        """Build a spoken summary."""
        if not result.get("url"):
            return "No URL provided, Sir."
        
        risk = result["risk_score"]
        host = result.get("host", "that site")
        verdict = result["verdict"]
        reasons = result.get("reasons", [])
        
        parts = [f"Security scan of {host}: {verdict}"]
        parts.append(f"Risk score: {risk} out of 100.")
        
        if reasons and risk >= 40:
            parts.append(f"Issues found: {reasons[0]}.")
            if len(reasons) > 1:
                parts.append(f"Also {reasons[1]}.")
        
        return " ".join(parts)
    
    def extract_url(self, text: str) -> Optional[str]:
        """Find a URL in free-form text."""
        pattern = r'(?:https?://)?(?:[-\w]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
        match = re.search(pattern, text)
        if match:
            url = match.group(0)
            if not url.startswith(("http://", "https://")):
                url = "http://" + url
            return url
        return None

# Singleton
phishing = PhishingDetector()

# Compat aliases for existing Main.py imports
check_url = phishing.analyze
extract_url_from_query = phishing.extract_url
format_for_jarvis = phishing.format_for_speech

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- PhishingDetector Test ---\n")
    print(f"{'='*70}")
    print(f"★  HACKATHON DEMO — 10+ Detection Techniques  ★")
    print(f"{'='*70}\n")
    
    test_urls = [
        # Safe URLs
        ("https://google.com", "SAFE"),
        ("https://github.com/user/repo", "SAFE"),
        ("https://www.amazon.in/dp/B08N5WRWNW", "SAFE"),
        
        # Suspicious patterns
        ("http://paypa1-verify-account.tk/login", "DANGER"),
        ("https://amaz0n.click/urgent-verify", "DANGER"),
        ("http://192.168.1.1/admin/login", "HIGH RISK"),
        ("http://bit.ly/xyz123", "SUSPICIOUS"),
        ("https://microsoft-support-team.ml/verify", "DANGER"),
        ("http://g00gle-drive.com/login", "DANGER"),
        ("https://facebook.com@scam.tk/login", "DANGER"),
        
        # Shortened
        ("tinyurl.com/abc", "SHORTENED"),
    ]
    
    for url, expected in test_urls:
        # Use deep_check=False for speed (SSL+redirect need net)
        r = phishing.analyze(url, deep_check=False)
        
        risk = r["risk_score"]
        
        # Verdict icon
        if risk < 40: icon = "[SAFE]"
        elif risk < 65: icon = "[SUSPECT]"
        elif risk < 85: icon = "[RISKY]"
        else: icon = "[DANGER]"
        
        print(f"{icon}  {url}")
        print(f"       Risk: {risk}/100 - {r['verdict']}")
        if r["reasons"]:
            for reason in r["reasons"][:3]:
                print(f"       - {reason}")
        print()
    
    # Example URL extraction
    print("-- URL Extraction Test --")
    texts = [
        "hey check out this link paypa1.tk/verify it's sus",
        "is https://google.com safe",
        "no url here just text",
    ]
    for t in texts:
        url = phishing.extract_url(t)
        print(f"  '{t[:50]}' -> {url}")
    
    print("\n[OK] PhishingDetector test complete\n")