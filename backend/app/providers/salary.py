"""Salary parsing (CLAUDE.md §10).

Display salary raw as posted; compute LPA **only for INR** postings — no FX
conversion. Parses "₹15 LPA", monthly INR, absolute annual INR, and ranges into
LPA where possible; "competitive"/absent/other currencies → no LPA (``None``).
Best-effort by design; ambiguous text yields ``None`` rather than a wrong number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_INR_MARKERS = ("₹", "inr", "rs.", "rs ", "rs/", "rupee", "lpa", "lakh", "lac", "crore")
_CURRENCY_SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "₹": "INR"}
_CURRENCY_WORDS = {"usd": "USD", "gbp": "GBP", "eur": "EUR", "inr": "INR"}
_NO_VALUE_WORDS = ("competitive", "negotiable", "depend", "as per", "market", "doe")
_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)(\s*k)?", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedSalary:
    raw: str | None
    currency: str | None
    lpa_min: Decimal | None
    lpa_max: Decimal | None


def _detect_currency(text: str, lower: str) -> str | None:
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    for word, code in _CURRENCY_WORDS.items():
        if re.search(rf"\b{word}\b", lower):
            return code
    if any(marker in lower for marker in _INR_MARKERS):
        return "INR"
    return None


def _unit(lower: str) -> str:
    if "crore" in lower or re.search(r"\bcr\b", lower):
        return "crore"
    if "lpa" in lower or "lakh" in lower or "lac" in lower:
        return "lakh"
    if "month" in lower or "/mo" in lower or "p.m" in lower or re.search(r"\bpm\b", lower):
        return "month"
    return "absolute"


def _to_lpa(value: Decimal, has_k: bool, unit: str) -> Decimal:
    if unit == "lakh":
        lpa = value
    elif unit == "crore":
        lpa = value * 100
    elif unit == "month":
        rupees = value * (1000 if has_k else 1)
        lpa = rupees * 12 / 100000
    else:  # absolute annual rupees
        rupees = value * (1000 if has_k else 1)
        lpa = rupees / 100000
    return lpa.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_salary(text: str | None) -> ParsedSalary:
    if not text or not text.strip():
        return ParsedSalary(raw=None, currency=None, lpa_min=None, lpa_max=None)

    raw = text.strip()
    lower = raw.lower()
    currency = _detect_currency(raw, lower)

    # LPA only for INR; other currencies keep the raw + code but no computed LPA.
    if currency != "INR" or any(w in lower for w in _NO_VALUE_WORDS):
        return ParsedSalary(raw=raw, currency=currency, lpa_min=None, lpa_max=None)

    unit = _unit(lower)
    cleaned = lower.replace(",", "")
    values: list[Decimal] = []
    for match in _NUMBER_RE.finditer(cleaned):
        number = Decimal(match.group(1))
        has_k = match.group(2) is not None
        values.append(_to_lpa(number, has_k, unit))

    if not values:
        return ParsedSalary(raw=raw, currency=currency, lpa_min=None, lpa_max=None)

    return ParsedSalary(raw=raw, currency=currency, lpa_min=min(values), lpa_max=max(values))
