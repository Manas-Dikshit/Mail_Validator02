from __future__ import annotations

from app.utils.data_loader import get_mx_provider_map


def lookup_mx_provider(mx_host: str) -> str | None:
    mx_host_lower = mx_host.lower().rstrip(".")
    for fragment, provider_name in get_mx_provider_map().items():
        if fragment in mx_host_lower:
            return provider_name
    return None
