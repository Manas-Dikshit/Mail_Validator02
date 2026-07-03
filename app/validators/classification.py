from __future__ import annotations

from app.utils.data_loader import (
    get_disposable_domains,
    get_free_providers,
    get_role_based_prefixes,
)


def is_disposable(domain: str) -> bool:
    domain = domain.lower()
    disposable = get_disposable_domains()
    if domain in disposable:
        return True
    # Catch simple subdomain wrapping, e.g. mail.mailinator.com
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in disposable:
            return True
    return False


def free_provider_name(domain: str) -> str | None:
    domain = domain.lower()
    providers = get_free_providers()
    return domain if domain in providers else None


def is_role_based(local_part: str) -> bool:
    local = local_part.lower().split("+")[0]  # ignore + tagging
    prefixes = get_role_based_prefixes()
    if local in prefixes:
        return True
    # local parts like "info-request" or "no.reply"
    normalized = local.replace(".", "").replace("-", "").replace("_", "")
    return normalized in {p.replace("-", "") for p in prefixes}


def is_business_email(disposable: bool, free: bool, mx_exists: bool) -> bool:
    return (not disposable) and (not free) and mx_exists
