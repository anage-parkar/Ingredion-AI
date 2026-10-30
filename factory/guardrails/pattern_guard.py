"""A deterministic, dependency-free guard for development and as a first filter.

It is **not** a substitute for Prompt Shields: it catches the obvious instruction
injections and oversize inputs, and lets Content Safety do the real work in Test
and Prod. Keeping it in the chain means Dev behaves like Prod when a document
carries "ignore previous instructions".
"""

from __future__ import annotations

import re

from .base import GuardResult

_INJECTION = [
    r"ignore (all |any )?(previous|prior|above) (instructions|directions|prompts?)",
    r"disregard (all |any )?(previous|prior|above) (instructions|directions)",
    r"you are now (a|an|the) ",
    r"(reveal|print|show|repeat) (your|the) (system|hidden|developer) prompt",
    r"act as (a|an) (?!.*(customer|supplier|buyer))",
    r"\bjailbreak\b",
    r"\bdo anything now\b",
    r"</?\s*(system|assistant|developer)\s*>",
    r"BEGIN (SYSTEM|ADMIN) (PROMPT|INSTRUCTIONS?)",
    r"create (a|the) (sales )?order (for|of) .* without (review|approval)",
]
_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _INJECTION]
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class PatternGuard:
    name = "pattern"

    def __init__(self, max_chars: int = 200_000) -> None:
        self.max_chars = max_chars

    def screen(self, text: str, *, purpose: str = "") -> GuardResult:
        reasons: list[str] = []
        if text is None:
            return GuardResult(True, self.name)
        if len(text) > self.max_chars:
            reasons.append(f"input too long ({len(text)} > {self.max_chars} chars)")
        if _CONTROL.search(text):
            reasons.append("control characters present")
        for pattern in _PATTERNS:
            if pattern.search(text):
                reasons.append(f"instruction-like text: /{pattern.pattern}/")
                break
        return GuardResult(not reasons, self.name, reasons)
