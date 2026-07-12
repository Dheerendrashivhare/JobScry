"""LLM client for match explanations and résumé tailoring (CLAUDE.md §2, §7, §11).

The LLM is an Infrastructure adapter used **after** scoring. It never produces or
influences a score (integrity rule §7) — it only explains one that already exists and
tailors a résumé. No key → these features are simply disabled and scoring still works.

Two providers behind one port, because the owner may supply either key (§2). Raw HTTP
via httpx rather than a vendor SDK: the app must speak both APIs with a per-user key,
and httpx is already the project's outbound HTTP layer.

Anthropic Messages API notes (verified against current docs):
- Endpoint POST /v1/messages, headers ``x-api-key`` + ``anthropic-version: 2023-06-01``.
- ``temperature``/``top_p`` are **rejected with a 400 on Opus 4.8** — do not send them.
- Response text lives in ``content[]`` blocks of ``type == "text"``.
- ``stop_reason == "refusal"`` returns HTTP 200 with no usable text — treat as no output.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.models.enums import LLMProvider

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

_EXPLAIN_SYSTEM = (
    "You are an honest technical recruiter. You are given a job and a candidate profile, "
    "plus a score that has ALREADY been computed by a deterministic engine. "
    "Explain that score. Do NOT dispute, recompute, or restate it as a different number. "
    "Be concise and specific about why the candidate does or does not fit. "
    "Never invent experience the candidate does not have."
)

_TAILOR_SYSTEM = (
    "You tailor résumés for a specific role. Rewrite ONLY using experience that already "
    "appears in the candidate's résumé — reorder, re-emphasise, and re-word for relevance. "
    "You must NOT fabricate employers, titles, dates, metrics, or skills. "
    "Every claim must remain defensible in an interview. "
    "If the résumé lacks something the job wants, leave it out rather than inventing it."
)


class LLMError(Exception):
    """The LLM call failed. Callers degrade gracefully — scoring is unaffected."""


@dataclass(frozen=True)
class LLMConfig:
    provider: LLMProvider
    api_key: str
    model: str | None = None

    @property
    def resolved_model(self) -> str:
        if self.model:
            return self.model
        return (
            DEFAULT_ANTHROPIC_MODEL
            if self.provider is LLMProvider.ANTHROPIC
            else DEFAULT_OPENAI_MODEL
        )


class LLMClient:
    def __init__(self, http: httpx.AsyncClient, config: LLMConfig) -> None:
        self.http = http
        self.config = config

    async def explain_match(self, prompt: str) -> str:
        return await self._complete(_EXPLAIN_SYSTEM, prompt, max_tokens=800)

    async def tailor_resume(self, prompt: str) -> str:
        return await self._complete(_TAILOR_SYSTEM, prompt, max_tokens=4000)

    async def _complete(self, system: str, prompt: str, *, max_tokens: int) -> str:
        if self.config.provider is LLMProvider.ANTHROPIC:
            return await self._anthropic(system, prompt, max_tokens)
        return await self._openai(system, prompt, max_tokens)

    async def _anthropic(self, system: str, prompt: str, max_tokens: int) -> str:
        payload = {
            "model": self.config.resolved_model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            # No temperature/top_p: rejected with a 400 on current Opus models.
        }
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        try:
            resp = await self.http.post(ANTHROPIC_URL, json=payload, headers=headers, timeout=120.0)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc

        if body.get("stop_reason") == "refusal":
            raise LLMError("Anthropic declined the request")

        text = "".join(
            block.get("text", "")
            for block in body.get("content", [])
            if block.get("type") == "text"
        ).strip()
        if not text:
            raise LLMError("Anthropic returned no text content")
        return text

    async def _openai(self, system: str, prompt: str, max_tokens: int) -> str:
        payload = {
            "model": self.config.resolved_model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = await self.http.post(OPENAI_URL, json=payload, headers=headers, timeout=120.0)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"OpenAI request failed: {exc}") from exc

        choices = body.get("choices") or []
        if not choices:
            raise LLMError("OpenAI returned no choices")
        text = (choices[0].get("message") or {}).get("content", "").strip()
        if not text:
            raise LLMError("OpenAI returned no text content")
        return text
