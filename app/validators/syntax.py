from __future__ import annotations

import re
import unicodedata

import idna
from email_validator import validate_email, EmailNotValidError, EmailSyntaxError

from app.config.settings import get_settings
from app.models.schemas import SyntaxResult

settings = get_settings()

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s")
_DOUBLE_DOT_RE = re.compile(r"\.\.")
_IP_LITERAL_RE = re.compile(r"^\[.*\]$")


def _basic_structural_checks(email: str) -> list[str]:
    """Cheap checks that run before handing off to the email-validator lib,
    so we can produce specific, human-readable reasons."""
    reasons: list[str] = []

    if not email or "@" not in email:
        reasons.append("Missing '@' symbol")
        return reasons

    if _CONTROL_CHAR_RE.search(email):
        reasons.append("Contains control characters")

    if _WHITESPACE_RE.search(email.strip("\n\r")) and " " in email.strip():
        reasons.append("Contains whitespace")

    local_part, _, domain_part = email.rpartition("@")

    if not local_part:
        reasons.append("Empty local part")
    if not domain_part:
        reasons.append("Empty domain part")

    if local_part.startswith(".") or local_part.endswith("."):
        reasons.append("Local part has leading or trailing dot")

    if domain_part.startswith(".") or domain_part.endswith("."):
        reasons.append("Domain has leading or trailing dot")

    if not local_part.startswith('"') and _DOUBLE_DOT_RE.search(local_part):
        reasons.append("Local part contains consecutive dots")

    if len(email) > settings.max_email_length:
        reasons.append(
            f"Total length {len(email)} exceeds max {settings.max_email_length}"
        )
    if len(local_part) > settings.max_local_part_length:
        reasons.append(
            f"Local part length {len(local_part)} exceeds max {settings.max_local_part_length}"
        )
    if len(domain_part) > settings.max_domain_length:
        reasons.append(
            f"Domain length {len(domain_part)} exceeds max {settings.max_domain_length}"
        )

    if _IP_LITERAL_RE.match(domain_part):
        reasons.append("Domain is an IP literal, not a hostname")

    return reasons


def validate_syntax(raw_email: str) -> SyntaxResult:
    email = (raw_email or "").strip()
    reasons = _basic_structural_checks(email)

    is_quoted = "@" in email and email.split("@", 1)[0].startswith('"')
    has_unicode = any(ord(ch) > 127 for ch in email)

    # Structural failures we consider fatal before even calling the library,
    # since email-validator can be lenient about some of these depending on
    # options (e.g. it won't flag IP literals unless configured to).
    fatal_prefixes = (
        "Missing '@'",
        "Empty local part",
        "Empty domain part",
        "Domain is an IP literal",
    )
    if any(r.startswith(fatal_prefixes) for r in reasons):
        return SyntaxResult(is_valid=False, is_unicode=has_unicode, reasons=reasons)

    try:
        result = validate_email(
    email,
    check_deliverability=False,
    allow_quoted_local=True,
    allow_smtputf8=True,
)
    except EmailSyntaxError as exc:
        reasons.append(str(exc))
        return SyntaxResult(
            is_valid=False, is_unicode=has_unicode, is_quoted_local_part=is_quoted, reasons=reasons
        )
    except EmailNotValidError as exc:
        reasons.append(str(exc))
        return SyntaxResult(
            is_valid=False, is_unicode=has_unicode, is_quoted_local_part=is_quoted, reasons=reasons
        )

    normalized = result.normalized
    local_part = result.local_part
    domain = result.domain

    # ASCII / punycode form of the domain (IDNA)
    ascii_domain = domain
    try:
        if has_unicode:
            ascii_domain = idna.encode(domain).decode("ascii")
        else:
            ascii_domain = domain
    except idna.IDNAError as exc:
        reasons.append(f"IDNA encoding failed: {exc}")
        return SyntaxResult(
            is_valid=False, is_unicode=has_unicode, is_quoted_local_part=is_quoted, reasons=reasons
        )

    # Length re-check against normalized/ascii forms (unicode may expand
    # under NFC normalization or punycode may exceed limits)
    if len(ascii_domain) > settings.max_domain_length:
        reasons.append("Domain exceeds max length after IDNA encoding")
        return SyntaxResult(
            is_valid=False, is_unicode=has_unicode, is_quoted_local_part=is_quoted, reasons=reasons
        )

    if reasons:
        # Non-fatal structural warnings collected earlier but the library
        # still accepted it (e.g. borderline dot rules for quoted parts) -
        # surface them without failing, unless they concern length/control
        # chars which are always fatal.
        hard_fail_markers = ("exceeds max", "control characters")
        if any(any(m in r for m in hard_fail_markers) for r in reasons):
            return SyntaxResult(
                is_valid=False,
                is_unicode=has_unicode,
                is_quoted_local_part=is_quoted,
                reasons=reasons,
            )

    return SyntaxResult(
        is_valid=True,
        normalized_email=unicodedata.normalize("NFC", normalized),
        local_part=local_part,
        domain=domain,
        ascii_domain=ascii_domain,
        is_unicode=has_unicode,
        is_quoted_local_part=is_quoted,
        reasons=[],
    )
