"""Unit tests for provider domain helpers: salary->LPA parsing, dedup, expiry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.enums import ProviderSlug
from app.providers.dedup import is_expired, make_dedup_key, normalize_url
from app.providers.salary import parse_salary


@pytest.mark.parametrize(
    ("text", "cur", "lo", "hi"),
    [
        ("₹15 LPA", "INR", Decimal("15.00"), Decimal("15.00")),
        ("12-18 LPA", "INR", Decimal("12.00"), Decimal("18.00")),
        ("₹15 lakh per annum", "INR", Decimal("15.00"), Decimal("15.00")),
        ("₹8,00,000 - ₹12,00,000 per annum", "INR", Decimal("8.00"), Decimal("12.00")),
        ("₹1,25,000/month", "INR", Decimal("15.00"), Decimal("15.00")),
        ("₹1.2 crore", "INR", Decimal("120.00"), Decimal("120.00")),
    ],
)
def test_parse_inr_to_lpa(text: str, cur: str, lo: Decimal, hi: Decimal) -> None:
    result = parse_salary(text)
    assert result.currency == cur
    assert result.lpa_min == lo
    assert result.lpa_max == hi
    assert result.raw == text


@pytest.mark.parametrize("text", ["Competitive", "Negotiable", "As per market", ""])
def test_no_value_salaries(text: str) -> None:
    result = parse_salary(text)
    assert result.lpa_min is None and result.lpa_max is None


def test_non_inr_currency_has_no_lpa() -> None:
    result = parse_salary("$120,000 per year")
    assert result.currency == "USD"
    assert result.lpa_min is None and result.lpa_max is None


def test_none_salary() -> None:
    result = parse_salary(None)
    assert result == parse_salary("")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.example.com/jobs/123?utm=x#top", "example.com/jobs/123"),
        ("http://Example.com/jobs/123/", "example.com/jobs/123"),
        ("boards.greenhouse.io/acme/jobs/42", "boards.greenhouse.io/acme/jobs/42"),
    ],
)
def test_normalize_url(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


def test_dedup_key_prefers_url_then_external_id() -> None:
    assert make_dedup_key("https://x.com/a?b=1") == "x.com/a"
    assert make_dedup_key(None, "abc", ProviderSlug.APIFY_LINKEDIN) == "apify_linkedin:abc"
    with pytest.raises(ValueError):
        make_dedup_key(None, None, None)


def test_is_expired() -> None:
    now = datetime(2026, 7, 11, tzinfo=UTC)
    assert is_expired(now - timedelta(days=1), now) is True
    assert is_expired(now + timedelta(days=1), now) is False
    assert is_expired(None, now) is False
    # naive datetime is treated as UTC
    assert is_expired(datetime(2026, 7, 10), now) is True
