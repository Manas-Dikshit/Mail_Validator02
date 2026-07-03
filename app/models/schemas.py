from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import (
    ValidationStatus,
    DnsStatus,
    Recommendation,
    SendDecision,
    CatchAllStatus,
    MailboxStatus,
)


class SyntaxResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_valid: bool
    normalized_email: Optional[str] = None
    local_part: Optional[str] = None
    domain: Optional[str] = None
    ascii_domain: Optional[str] = None  # punycode / IDNA form
    is_unicode: bool = False
    is_quoted_local_part: bool = False
    reasons: list[str] = Field(default_factory=list)


class DnsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    domain_exists: bool = False
    mx_exists: bool = False
    mx_hosts: list[str] = Field(default_factory=list)
    used_a_fallback: bool = False
    status: DnsStatus = DnsStatus.SKIPPED
    response_time_ms: Optional[float] = None
    mx_provider: Optional[str] = None
    has_spf: bool = False
    has_dmarc: bool = False
    has_dkim_indicator: bool = False
    from_cache: bool = False
    error: Optional[str] = None


class UnicodeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    has_unicode: bool = False
    mixed_scripts: bool = False
    has_invisible_chars: bool = False
    has_rtl_markers: bool = False
    possible_homograph: bool = False
    notes: list[str] = Field(default_factory=list)


class EmailValidationResult(BaseModel):
    """Full result for a single email address."""

    model_config = ConfigDict(frozen=False)

    original_email: str
    normalized_email: Optional[str] = None

    validation_status: ValidationStatus = ValidationStatus.UNKNOWN
    primary_tag: str = ""
    secondary_tag: str = ""

    syntax_valid: bool = False
    domain_exists: bool = False
    mx_exists: bool = False
    dns_status: DnsStatus = DnsStatus.SKIPPED

    disposable: bool = False
    role_based: bool = False
    free_provider: bool = False
    free_provider_name: Optional[str] = None
    business_email: bool = False
    international: bool = False

    typo_suggestion: Optional[str] = None

    catch_all_status: CatchAllStatus = CatchAllStatus.UNKNOWN
    mailbox_status: MailboxStatus = MailboxStatus.MAILBOX_UNKNOWN

    spam_score: int = 0
    risk_score: int = 0
    reason: str = ""
    recommendation: Recommendation = Recommendation.HIGH_RISK

    # Deliverability extensions
    deliverability_score: int = 0
    send_decision: SendDecision = SendDecision.REVIEW
    domain_reputation_flags: list[str] = Field(default_factory=list)
    has_spf: bool = False
    has_dkim_indicator: bool = False
    has_dmarc: bool = False
    mx_provider: Optional[str] = None
    dns_response_time_ms: Optional[float] = None
    validation_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    duplicate_count: int = 1

    def to_flat_dict(self) -> dict:
        """Flatten enums to plain strings for DataFrame / xlsx export."""
        d = self.model_dump()
        for k, v in list(d.items()):
            if hasattr(v, "value"):
                d[k] = v.value
        return d


class ValidationJobSummary(BaseModel):
    total_rows: int
    processed_rows: int
    valid_count: int
    invalid_count: int
    unknown_count: int
    duplicate_count: int
    elapsed_seconds: float
