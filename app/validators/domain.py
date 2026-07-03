from __future__ import annotations

import tldextract

from app.utils.data_loader import get_reserved_domains

# tldextract ships its own public suffix list snapshot; disable live fetches
# so the app stays fully offline-safe for this check.
_extractor = tldextract.TLDExtract(suffix_list_urls=())

_RESERVED_TLDS = {"invalid", "test", "example", "localhost", "local", "internal"}


def check_reserved_or_invalid_domain(domain: str) -> tuple[bool, str | None]:
    """Returns (is_reserved_or_invalid, reason)."""
    domain_lower = domain.lower().rstrip(".")

    if domain_lower in get_reserved_domains():
        return True, f"'{domain_lower}' is a known reserved/placeholder domain"

    ext = _extractor(domain_lower)
    tld = ext.suffix

    if not tld:
        return True, "Domain has no valid public suffix / TLD"

    top_label = tld.split(".")[-1]
    if top_label in _RESERVED_TLDS:
        return True, f"'.{top_label}' is a reserved/non-routable TLD"

    if domain_lower in {"example.com", "example.net", "example.org"}:
        return True, "Documentation/example domain per RFC 2606"

    return False, None


def registrable_domain(domain: str) -> str:
    ext = _extractor(domain.lower().rstrip("."))
    return ext.registered_domain or domain.lower()
