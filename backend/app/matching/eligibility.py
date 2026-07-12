"""Work-authorization logic (CLAUDE.md §8).

The candidate is India-based: India roles (any mode) and India-eligible remote roles
are **actionable now**. Offshore roles are flagged **eligibility-gated** unless the
posting explicitly offers sponsorship or relocation — willingness to relocate is not
the same as being work-authorized, and we never encourage a false declaration.

Gating is reported honestly alongside the score; it does not silently delete the job.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import EligibilityStatus

_INDIA_TOKENS = (
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "mumbai",
    "delhi",
    "noida",
    "gurugram",
    "gurgaon",
    "chennai",
    "kolkata",
    "ahmedabad",
)
_GLOBAL_REMOTE_TOKENS = ("worldwide", "anywhere", "global", "remote")
_SPONSORSHIP_TOKENS = (
    "visa sponsorship",
    "will sponsor",
    "sponsorship available",
    "we sponsor",
    "relocation assistance",
    "relocation support",
    "relocation provided",
)
_NO_SPONSORSHIP_TOKENS = (
    "no sponsorship",
    "not able to sponsor",
    "cannot sponsor",
    "without sponsorship",
    "no visa sponsorship",
    "must be authorized to work in",
    "must be eligible to work in",
    "citizens only",
    "work permit required",
)


@dataclass(frozen=True)
class EligibilityResult:
    status: EligibilityStatus
    reason: str

    @property
    def actionable(self) -> bool:
        return self.status is EligibilityStatus.ACTIONABLE


def assess_eligibility(
    location: str | None,
    is_remote: bool,
    description: str | None = None,
    visa_sponsorship: bool | None = None,
) -> EligibilityResult:
    location_text = (location or "").lower()
    full_text = f"{location_text} {(description or '').lower()}"

    if any(token in location_text for token in _INDIA_TOKENS):
        return EligibilityResult(EligibilityStatus.ACTIONABLE, "India-based role")

    if visa_sponsorship is True or any(t in full_text for t in _SPONSORSHIP_TOKENS):
        return EligibilityResult(
            EligibilityStatus.ACTIONABLE, "Posting offers sponsorship/relocation"
        )

    explicitly_blocked = any(t in full_text for t in _NO_SPONSORSHIP_TOKENS)

    if is_remote or any(t in location_text for t in _GLOBAL_REMOTE_TOKENS):
        if explicitly_blocked:
            return EligibilityResult(
                EligibilityStatus.ELIGIBILITY_GATED,
                "Remote role explicitly excludes candidates needing sponsorship",
            )
        return EligibilityResult(
            EligibilityStatus.ACTIONABLE, "Remote role with no stated work-auth restriction"
        )

    return EligibilityResult(
        EligibilityStatus.ELIGIBILITY_GATED,
        "Offshore role with no stated sponsorship — raise eligibility with the recruiter",
    )
