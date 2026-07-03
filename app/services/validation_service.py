from __future__ import annotations

import logging

from app.dns.resolver import resolve_domain, DnsLookupOutcome
from app.models.enums import ValidationStatus, MailboxStatus, DnsStatus, CatchAllStatus
from app.models.schemas import EmailValidationResult
from app.services.catch_all import estimate_catch_all
from app.services.risk_scoring import (
    compute_risk_score,
    compute_deliverability_score,
    determine_recommendation,
    determine_send_decision,
)
from app.validators.classification import (
    is_disposable,
    free_provider_name,
    is_role_based,
    is_business_email,
)
from app.validators.domain import check_reserved_or_invalid_domain
from app.validators.spam import compute_spam_score
from app.validators.syntax import validate_syntax
from app.validators.typo import suggest_domain_correction
from app.validators.unicode_checks import analyze_unicode

logger = logging.getLogger(__name__)


def _build_invalid_result(
    original_email: str,
    status: ValidationStatus,
    reasons: list[str],
    *,
    typo_suggestion: str | None = None,
) -> EmailValidationResult:
    reason_text = "; ".join(reasons) if reasons else "Invalid email"
    return EmailValidationResult(
        original_email=original_email,
        validation_status=status,
        primary_tag="INVALID",
        secondary_tag=status.value,
        syntax_valid=False,
        typo_suggestion=typo_suggestion,
        reason=reason_text,
        risk_score=100,
        deliverability_score=0,
        recommendation=determine_recommendation(status, 100),
        send_decision=determine_send_decision(determine_recommendation(status, 100)),
    )


def validate_single_email(
    raw_email: str, *, check_dns: bool = True, deep_dns_checks: bool = True
) -> EmailValidationResult:
    original = (raw_email or "").strip()

    if not original:
        return _build_invalid_result(original, ValidationStatus.INVALID_SYNTAX, ["Empty value"])

    syntax = validate_syntax(original)
    if not syntax.is_valid:
        # Route to the most specific status we can infer from the reasons.
        status = ValidationStatus.INVALID_SYNTAX
        joined = " ".join(syntax.reasons).lower()
        if "length" in joined:
            status = ValidationStatus.INVALID_LENGTH
        elif "control charact" in joined:
            status = ValidationStatus.INVALID_CONTROL_CHARACTER
        elif "local part" in joined:
            status = ValidationStatus.INVALID_LOCAL_PART
        elif "domain" in joined and "ip literal" in joined:
            status = ValidationStatus.INVALID_IP_LITERAL
        elif "domain" in joined:
            status = ValidationStatus.INVALID_DOMAIN_PART
        return _build_invalid_result(original, status, syntax.reasons)

    domain = syntax.ascii_domain or syntax.domain
    local_part = syntax.local_part or original.split("@")[0]

    # Typo suggestion is computed early so it can be surfaced even when the
    # domain is ultimately rejected for an unrecognized/invalid TLD.
    typo_suggestion = suggest_domain_correction(domain)

    # --- Reserved / placeholder / invalid-TLD domains ---
    is_reserved, reserved_reason = check_reserved_or_invalid_domain(domain)
    if is_reserved:
        reason_lower = (reserved_reason or "").lower()
        if "example" in reason_lower:
            status = ValidationStatus.INVALID_EXAMPLE_DOMAIN
        elif "no valid public suffix" in reason_lower or "reserved/non-routable tld" in reason_lower:
            status = ValidationStatus.INVALID_TLD
        else:
            status = ValidationStatus.INVALID_RESERVED_DOMAIN
        reasons = [reserved_reason or "Reserved domain"]
        if typo_suggestion:
            reasons.append(f"Possible typo, did you mean '{typo_suggestion}'?")
        return _build_invalid_result(original, status, reasons, typo_suggestion=typo_suggestion)

    # --- Unicode / homograph analysis ---
    unicode_result = analyze_unicode(original)
    if unicode_result.has_invisible_chars:
        return _build_invalid_result(
            original,
            ValidationStatus.INVALID_UNICODE,
            ["Contains invisible/zero-width characters"],
        )

    # --- Classification (disposable / role / free / business) ---
    disposable = is_disposable(domain)
    role = is_role_based(local_part)
    free_provider = free_provider_name(domain)
    spam_score, spam_reasons = compute_spam_score(local_part)

    # --- DNS ---
    dns_outcome = DnsLookupOutcome(status=DnsStatus.SKIPPED)
    if check_dns:
        dns_outcome = resolve_domain(domain, deep_checks=deep_dns_checks)

    domain_exists = dns_outcome.domain_exists
    mx_exists = dns_outcome.mx_exists
    business = is_business_email(disposable, bool(free_provider), mx_exists)

    reasons: list[str] = list(syntax.reasons)
    reasons.extend(spam_reasons)
    reasons.extend(unicode_result.notes)
    if disposable:
        reasons.append("Domain is a known disposable/temporary email provider")
    if role:
        reasons.append("Local part matches a role-based mailbox pattern")
    if typo_suggestion:
        reasons.append(f"Possible typo, did you mean '{typo_suggestion}'?")
    if check_dns and dns_outcome.error:
        reasons.append(f"DNS error: {dns_outcome.error}")

    # --- Determine validation status ---
    if check_dns and not domain_exists:
        status = ValidationStatus.INVALID_DOMAIN
    elif disposable:
        status = ValidationStatus.INVALID_DISPOSABLE
    elif check_dns and not mx_exists:
        status = ValidationStatus.INVALID_MX
    elif role:
        status = ValidationStatus.INVALID_ROLE
    elif unicode_result.possible_homograph:
        status = ValidationStatus.SUSPICIOUS
    elif spam_score >= 60:
        status = ValidationStatus.RISKY
    elif free_provider:
        status = ValidationStatus.VALID_FREE
    elif business:
        status = ValidationStatus.VALID_BUSINESS
    elif not check_dns:
        status = ValidationStatus.VALID  # syntax-only mode
    else:
        status = ValidationStatus.VALID_HIGH_CONFIDENCE

    primary_tag = status.value.split("_")[0]
    secondary_tag = "DISPOSABLE" if disposable else ("ROLE_BASED" if role else (
        "FREE_PROVIDER" if free_provider else ("BUSINESS" if business else "GENERAL")
    ))

    risk_score = compute_risk_score(
        syntax_valid=True,
        domain_exists=domain_exists if check_dns else True,
        mx_exists=mx_exists if check_dns else True,
        disposable=disposable,
        role_based=role,
        free_provider=bool(free_provider),
        business_email=business,
        spam_score=spam_score,
        has_unicode=unicode_result.has_unicode,
        possible_homograph=unicode_result.possible_homograph,
        has_typo_suggestion=bool(typo_suggestion),
    )
    deliverability_score = compute_deliverability_score(
        risk_score=risk_score,
        has_spf=dns_outcome.has_spf,
        has_dmarc=dns_outcome.has_dmarc,
        has_dkim_indicator=dns_outcome.has_dkim_indicator,
        mx_exists=mx_exists if check_dns else True,
    )
    recommendation = determine_recommendation(status, risk_score)
    send_decision = determine_send_decision(recommendation)

    domain_rep_flags: list[str] = []
    if disposable:
        domain_rep_flags.append("DISPOSABLE_DOMAIN")
    if unicode_result.possible_homograph:
        domain_rep_flags.append("POSSIBLE_HOMOGRAPH")
    if typo_suggestion:
        domain_rep_flags.append("POSSIBLE_TYPO")
    if check_dns and not mx_exists:
        domain_rep_flags.append("NO_MX_RECORD")

    catch_all = estimate_catch_all(dns_outcome.mx_hosts) if check_dns else CatchAllStatus.UNKNOWN

    return EmailValidationResult(
        original_email=original,
        normalized_email=syntax.normalized_email,
        validation_status=status,
        primary_tag=primary_tag,
        secondary_tag=secondary_tag,
        syntax_valid=True,
        domain_exists=domain_exists,
        mx_exists=mx_exists,
        dns_status=dns_outcome.status,
        disposable=disposable,
        role_based=role,
        free_provider=bool(free_provider),
        free_provider_name=free_provider,
        business_email=business,
        international=unicode_result.has_unicode,
        typo_suggestion=typo_suggestion,
        catch_all_status=catch_all,
        mailbox_status=MailboxStatus.MAILBOX_UNKNOWN,
        spam_score=spam_score,
        risk_score=risk_score,
        reason="; ".join(reasons) if reasons else "No issues detected",
        recommendation=recommendation,
        deliverability_score=deliverability_score,
        send_decision=send_decision,
        domain_reputation_flags=domain_rep_flags,
        has_spf=dns_outcome.has_spf,
        has_dkim_indicator=dns_outcome.has_dkim_indicator,
        has_dmarc=dns_outcome.has_dmarc,
        mx_provider=dns_outcome.mx_provider,
        dns_response_time_ms=dns_outcome.response_time_ms,
    )
