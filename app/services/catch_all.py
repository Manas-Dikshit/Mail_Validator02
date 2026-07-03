from __future__ import annotations

from app.models.enums import CatchAllStatus

# Hosting/MX patterns that are *commonly* configured with catch-all mailboxes
# in shared-hosting setups. This is a weak signal, not a verification - we
# never claim certainty here, per the project's mailbox-verification limits.
_CATCH_ALL_PRONE_MX_FRAGMENTS = (
    "improvmx.com",
    "forwardemail.net",
    "zoho.com",
    "secureserver.net",  # GoDaddy shared hosting
    "bluehost.com",
    "hostgator.com",
    "dreamhost.com",
)


def estimate_catch_all(mx_hosts: list[str]) -> CatchAllStatus:
    """Returns a *non-authoritative* estimate. Never returns a confirmed
    state - actual catch-all detection requires live SMTP RCPT TO probing
    against a random, non-existent mailbox, which this offline tool does
    not perform (see README limitations)."""
    if not mx_hosts:
        return CatchAllStatus.UNKNOWN

    for host in mx_hosts:
        host_lower = host.lower()
        if any(fragment in host_lower for fragment in _CATCH_ALL_PRONE_MX_FRAGMENTS):
            return CatchAllStatus.POSSIBLE_CATCH_ALL

    return CatchAllStatus.UNKNOWN
