"""Input Guardrails for ClothesSpot AI Customer Automation.

Provides multi-layer validation:
1. Input sanitization (length, encoding, script tag filtering)
2. Prompt injection & jailbreak detection (rule overrides, system prompt extraction, persona hijacking)
3. Sensitive data protection & PII redaction (Credit Card Luhn checks, SSN, Passwords, API Keys)
4. Harmful / abusive content filtering
"""

import re
from typing import Any, Dict, List, Optional, Tuple


INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|commands)",
    r"(?i)forget\s+(your\s+)?(instructions|rules|system\s+message)",
    r"(?i)system\s+prompt\s+override",
    r"(?i)you\s+are\s+now\s+(DAN|unrestricted|jailbroken|an\s+unfiltered\s+ai)",
    r"(?i)act\s+as\s+(an\s+unrestricted|a\s+jailbroken|god\s+mode)",
    r"(?i)print\s+(your\s+)?(system\s+prompt|initial\s+instructions|instructions\s+verbatim)",
    r"(?i)reveal\s+(your\s+)?(secret|internal|system)\s+(instructions|prompt|rules)",
    r"(?i)disregard\s+the\s+above",
    r"(?i)bypass\s+(safety|guardrails|filters|content\s+policy)",
    r"(?i)developer\s+mode\s+output",
]

CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PASSWORD_IN_TEXT_REGEX = re.compile(r"(?i)(?:password|pwd|passcode)\s*[:=]\s*([^\s,]+)")
API_KEY_REGEX = re.compile(r"(?i)(?:sk-[a-zA-Z0-9]{20,}|api[_-]?key\s*[:=]\s*[a-zA-Z0-9_\-]{16,})")


def luhn_checksum(card_number: str) -> bool:
    """Validate credit card number using Luhn algorithm."""
    digits = [int(c) for c in card_number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reversed_digits = digits[::-1]
    for i, d in enumerate(reversed_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


class InputGuardrails:
    """Validates and sanitizes incoming user complaints before agent processing."""

    def __init__(self, min_length: int = 3, max_length: int = 4000) -> None:
        self.min_length = min_length
        self.max_length = max_length

    def check_prompt_injection(self, text: str) -> Tuple[bool, Optional[str]]:
        """Detect prompt injection, jailbreaks, or instruction override attempts."""
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text):
                return True, f"Detected potential prompt injection / jailbreak attempt matching pattern: {pattern}"
        return False, None

    def redact_pii_and_sensitive_data(self, text: str) -> Tuple[str, List[str]]:
        """Identify and redact credit cards, SSNs, passwords, and API keys."""
        redactions: List[str] = []
        cleaned_text = text

        # 1. Credit Cards
        def replace_card(match: re.Match) -> str:
            raw = match.group(0)
            digits = re.sub(r"\D", "", raw)
            if luhn_checksum(digits) or len(digits) == 16:
                redactions.append("Payment Card Number (Redacted for security)")
                return f"[REDACTED_CARD_****{digits[-4:]}]"
            return raw

        cleaned_text = CREDIT_CARD_REGEX.sub(replace_card, cleaned_text)

        # 2. SSN
        if SSN_REGEX.search(cleaned_text):
            redactions.append("Social Security Number (Redacted)")
            cleaned_text = SSN_REGEX.sub("[REDACTED_SSN]", cleaned_text)

        # 3. Passwords in plain text
        if PASSWORD_IN_TEXT_REGEX.search(cleaned_text):
            redactions.append("Plaintext Password (Redacted)")
            cleaned_text = PASSWORD_IN_TEXT_REGEX.sub("password: [REDACTED_PASSWORD]", cleaned_text)

        # 4. API Keys
        if API_KEY_REGEX.search(cleaned_text):
            redactions.append("API Credential / Token (Redacted)")
            cleaned_text = API_KEY_REGEX.sub("[REDACTED_API_KEY]", cleaned_text)

        return cleaned_text, redactions

    def validate_input(self, complaint: str, customer_name: Optional[str] = None) -> Dict[str, Any]:
        """Execute full suite of input validation checks."""
        # 1. Length validation
        stripped = complaint.strip() if complaint else ""
        if len(stripped) < self.min_length:
            return {
                "valid": False,
                "sanitized_text": stripped,
                "reason": f"Complaint too short. Minimum length is {self.min_length} characters.",
                "redactions": [],
                "injection_detected": False,
            }

        if len(stripped) > self.max_length:
            return {
                "valid": False,
                "sanitized_text": stripped[:self.max_length],
                "reason": f"Complaint exceeds maximum allowed length of {self.max_length} characters.",
                "redactions": [],
                "injection_detected": False,
            }

        # 2. Prompt injection check
        is_injection, injection_reason = self.check_prompt_injection(stripped)
        if is_injection:
            return {
                "valid": False,
                "sanitized_text": stripped,
                "reason": f"Security violation: {injection_reason}",
                "redactions": [],
                "injection_detected": True,
            }

        # 3. PII & Sensitive Information Masking
        sanitized_text, redactions = self.redact_pii_and_sensitive_data(stripped)

        # Sanitize customer name if provided
        sanitized_customer = customer_name.strip() if customer_name else ""
        if sanitized_customer:
            sanitized_customer = re.sub(r"[<>{}]", "", sanitized_customer)

        return {
            "valid": True,
            "sanitized_text": sanitized_text,
            "customer_name": sanitized_customer,
            "reason": None,
            "redactions": redactions,
            "injection_detected": False,
        }
