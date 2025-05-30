import re
import json
import logging
from typing import Dict, Tuple, List, Set
from ..database.models import ServerSettings
from ..config import GENERATION_LIMITS

class ContentFilter:
    def __init__(self):
        # Load filter patterns
        self.jailbreak_patterns: Set[str] = {
            r"ignore previous instructions",
            r"ignore all rules",
            r"ignore your rules",
            r"ignore your programming",
            r"ignore your ethical constraints",
            r"bypass your filters",
            r"disable your filters",
            r"override your settings",
            r"change your personality",
            r"new personality",
            r"act as a different",
            r"pretend you are",
            r"stop being",
            r"don't be",
            r"ignore your role",
            r"break character",
            r"exit character",
            r"leave character",
            r"drop character"
        }

        # Mature content patterns
        self.mature_patterns: Dict[int, Set[str]] = {
            1: {  # Mild
                r"\b(damn|hell|crap)\b",
                r"\b(stupid|idiot|dumb)\b",
                r"\b(suck|sucks|sucking)\b"
            },
            2: {  # Moderate
                r"\b(fuck|shit|bitch|ass)\b",
                r"\b(dick|cock|pussy)\b",
                r"\b(nsfw|lewd|kinky)\b"
            },
            3: {  # Advanced
                r"\b(explicit sexual terms)\b",
                r"\b(extreme violence terms)\b",
                r"\b(hardcore content terms)\b"
            }
        }

        # Safety patterns
        self.unsafe_patterns: Set[str] = {
            r"(sudo|rm -rf|del /f|format c:|mkfs)",  # System commands
            r"(hack|crack|exploit|breach)",  # Security terms
            r"(ddos|dos attack|flood attack)",  # Attack terms
            r"(private key|password|credential)",  # Sensitive data
            r"(token|api key|secret key)",  # API security
            r"(social security|credit card|bank account)",  # Personal info
            r"(dox|doxx|personal info)",  # Privacy violation
            r"(gore|torture|murder)",  # Extreme violence
            r"(cp|csam)",  # Illegal content
            r"(token grab|ip grab|ip logger)"  # Malicious tools
        }

    def detect_jailbreak(self, text: str) -> Tuple[bool, str]:
        """
        Detect potential jailbreak attempts in the text.
        Returns (is_jailbreak, reason)
        """
        text = text.lower()
        
        # Check for direct jailbreak patterns
        for pattern in self.jailbreak_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"Detected jailbreak attempt pattern: {pattern}"

        # Check for suspicious combinations
        suspicious_pairs = [
            (r"system prompt", r"change|modify|update|ignore"),
            (r"instructions", r"ignore|bypass|override"),
            (r"settings", r"change|modify|override"),
            (r"character", r"change|switch|modify")
        ]
        
        for base, modifier in suspicious_pairs:
            if re.search(f"{base}.*{modifier}|{modifier}.*{base}", text, re.IGNORECASE):
                return True, f"Detected suspicious combination: {base} + {modifier}"

        # Check for repetitive patterns that might be trying to overflow or confuse
        if len(re.findall(r"(\b\w+\b)\s+\1{3,}", text)):
            return True, "Detected repetitive pattern attempt"

        return False, ""

    def check_mature_content(self, text: str, server_settings: Dict) -> Tuple[bool, int]:
        """
        Check if text contains mature content and at what level.
        Returns (contains_mature, level)
        """
        if not server_settings.get("mature_enabled", False):
            # Check against all patterns if mature content is disabled
            for level in range(1, 4):
                for pattern in self.mature_patterns[level]:
                    if re.search(pattern, text, re.IGNORECASE):
                        return True, level
            return False, 0

        # If mature content is enabled, only flag content above the allowed level
        allowed_level = server_settings.get("mature_level", 1)
        for level in range(allowed_level + 1, 4):
            for pattern in self.mature_patterns[level]:
                if re.search(pattern, text, re.IGNORECASE):
                    return True, level
        return False, 0

    def is_safe_content(self, text: str) -> Tuple[bool, str]:
        """
        Check if the content is safe (no dangerous patterns).
        Returns (is_safe, reason)
        """
        text = text.lower()
        
        # Check against unsafe patterns
        for pattern in self.unsafe_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False, f"Detected unsafe content pattern"

        # Check for potential command injection
        if re.search(r"[;&|`$]", text):
            return False, "Detected potential command injection characters"

        # Check for excessive length
        if len(text) > GENERATION_LIMITS["max_response_length"]:
            return False, "Content exceeds maximum allowed length"

        # Check for spam-like content
        if re.search(r"(.)\1{10,}", text):
            return False, "Detected spam-like repetitive content"

        return True, ""

    async def filter_message(self, text: str, server_id: str = None) -> Dict:
        """
        Comprehensive message filtering.
        Returns a dictionary with all check results.
        """
        # Get server settings if server_id is provided
        server_settings = {}
        if server_id:
            try:
                result = ServerSettings.execute_query(
                    "SELECT * FROM filter_settings WHERE server_id = ?",
                    (server_id,),
                    fetch=True
                )
                if result:
                    server_settings = {
                        "filter_enabled": bool(result[0][1]),
                        "mature_enabled": bool(result[0][2]),
                        "mature_level": int(result[0][3])
                    }
            except Exception as e:
                logging.error(f"Error fetching server settings: {e}")

        # Perform all checks
        is_jailbreak, jailbreak_reason = self.detect_jailbreak(text)
        has_mature, mature_level = self.check_mature_content(text, server_settings)
        is_safe, safety_reason = self.is_safe_content(text)

        return {
            "is_filtered": is_jailbreak or (has_mature and not server_settings.get("mature_enabled", False)) or not is_safe,
            "checks": {
                "jailbreak": {
                    "detected": is_jailbreak,
                    "reason": jailbreak_reason if is_jailbreak else ""
                },
                "mature_content": {
                    "detected": has_mature,
                    "level": mature_level,
                    "allowed": server_settings.get("mature_enabled", False)
                },
                "safety": {
                    "is_safe": is_safe,
                    "reason": safety_reason if not is_safe else ""
                }
            },
            "server_settings": server_settings
        }

# Global content filter instance
content_filter = ContentFilter() 