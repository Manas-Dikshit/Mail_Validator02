from __future__ import annotations

from app.models.enums import Recommendation, SendDecision, ValidationStatus


def compute_risk_score(
    *,
    syntax_valid: bool,
    domain_exists: bool,
    mx_exists: bool,
    disposable: bool,
    role_based: bool,
    free_provider: bool,
    business_email: bool,
    spam_score: int,
    has_unicode: bool,
    possible_homograph: bool,
    has_typo_suggestion: bool,
) -> int:
    """0 = safest, 100 = highest risk."""
    if not syntax_valid:
        return 100

    risk = 0

    if not domain_exists:
        risk += 45
    if domain_exists and not mx_exists:
        risk += 30
    if disposable:
        risk += 40
    if role_based:
        risk += 15
    if possible_homograph:
        risk += 25
    if has_typo_suggestion:
        risk += 15
    if has_unicode and not possible_homograph:
        risk += 3  # unicode itself is not risky, just noted

    risk += round(spam_score * 0.3)

    if business_email and domain_exists and mx_exists:
        risk -= 10
    if free_provider and not disposable:
        risk -= 5

    return max(0, min(100, risk))


def compute_deliverability_score(
    *,
    risk_score: int,
    has_spf: bool,
    has_dmarc: bool,
    has_dkim_indicator: bool,
    mx_exists: bool,
) -> int:
    """0 = do not mail, 100 = excellent deliverability confidence."""
    score = 100 - risk_score
    if not mx_exists:
        score -= 20
    if has_spf:
        score += 5
    if has_dmarc:
        score += 5
    if has_dkim_indicator:
        score += 3
    return max(0, min(100, score))


def determine_recommendation(
    validation_status: ValidationStatus, risk_score: int
) -> Recommendation:
    """
    Hard rule: any INVALID_* validation status must never be recommended for sending.
    Use explicit enum checks to avoid fragile string-prefix behavior.
    """
    invalid_prefix = str(validation_status.value).startswith("INVALID_")
    is_invalid = validation_status in {ValidationStatus.INVALID} or invalid_prefix
    if is_invalid:
        return Recommendation.INVALID

    if risk_score <= 15:
        return Recommendation.SAFE_TO_SEND
    if risk_score <= 35:
        return Recommendation.LIKELY_SAFE
    if risk_score <= 60:
        return Recommendation.SEND_WITH_CAUTION
    if risk_score <= 85:
        return Recommendation.HIGH_RISK
    return Recommendation.DO_NOT_SEND


def determine_send_decision(recommendation: Recommendation) -> SendDecision:
    mapping = {
        Recommendation.SAFE_TO_SEND: SendDecision.SEND,
        Recommendation.LIKELY_SAFE: SendDecision.SEND,
        Recommendation.SEND_WITH_CAUTION: SendDecision.REVIEW,
        Recommendation.HIGH_RISK: SendDecision.REVIEW,
        Recommendation.DO_NOT_SEND: SendDecision.SKIP,
        Recommendation.INVALID: SendDecision.SKIP,
    }
    return mapping[recommendation]
