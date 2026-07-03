from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import dns.resolver
import dns.exception

from app.config.settings import get_settings
from app.dns.cache import TTLCache
from app.models.enums import DnsStatus
from app.utils.mx_provider import lookup_mx_provider

logger = logging.getLogger(__name__)
settings = get_settings()

_dns_cache = TTLCache(
    max_size=settings.dns_cache_max_size, default_ttl=settings.dns_cache_ttl_seconds
)


@dataclass
class DnsLookupOutcome:
    domain_exists: bool = False
    mx_exists: bool = False
    mx_hosts: list[str] = field(default_factory=list)
    used_a_fallback: bool = False
    status: DnsStatus = DnsStatus.SKIPPED
    response_time_ms: Optional[float] = None
    mx_provider: Optional[str] = None
    has_spf: bool = False
    has_dmarc: bool = False
    has_dkim_indicator: bool = False
    from_cache: bool = False
    error: Optional[str] = None


def _build_resolver() -> "dns.resolver.Resolver":
    resolver = dns.resolver.Resolver(configure=True)
    if settings.dns_nameservers:
        resolver.nameservers = settings.dns_nameservers
    resolver.timeout = settings.dns_timeout_seconds
    resolver.lifetime = settings.dns_lifetime_seconds
    return resolver


def _query_with_retry(resolver: "dns.resolver.Resolver", domain: str, rdtype: str):
    last_exc: Optional[Exception] = None
    for attempt in range(settings.dns_max_retries + 1):
        try:
            return resolver.resolve(domain, rdtype)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            raise
        except dns.exception.Timeout as exc:
            last_exc = exc
        except Exception as exc:  # noqa: BLE001 - broad on purpose, DNS lib raises many
            last_exc = exc
        if attempt < settings.dns_max_retries:
            time.sleep(settings.dns_retry_backoff_seconds * (attempt + 1))
    if last_exc:
        raise last_exc
    raise dns.exception.DNSException("Unknown DNS failure")


def _check_spf_dmarc(resolver: "dns.resolver.Resolver", domain: str) -> tuple[bool, bool]:
    has_spf = False
    has_dmarc = False
    try:
        txt_answers = _query_with_retry(resolver, domain, "TXT")
        for rdata in txt_answers:
            txt = b"".join(rdata.strings).decode("utf-8", errors="ignore") if hasattr(
                rdata, "strings"
            ) else str(rdata)
            if txt.lower().startswith("v=spf1"):
                has_spf = True
    except Exception:  # noqa: BLE001
        pass
    try:
        dmarc_answers = _query_with_retry(resolver, f"_dmarc.{domain}", "TXT")
        for rdata in dmarc_answers:
            txt = b"".join(rdata.strings).decode("utf-8", errors="ignore") if hasattr(
                rdata, "strings"
            ) else str(rdata)
            if txt.lower().startswith("v=dmarc1"):
                has_dmarc = True
    except Exception:  # noqa: BLE001
        pass
    return has_spf, has_dmarc


def _check_dkim_indicator(resolver: "dns.resolver.Resolver", domain: str) -> bool:
    """Best-effort only. DKIM selectors are arbitrary; we only probe a few
    conventional selector names. Absence of a hit does NOT mean DKIM is
    not configured."""
    common_selectors = ["default", "selector1", "selector2", "google", "k1", "mail"]
    for selector in common_selectors:
        try:
            _query_with_retry(resolver, f"{selector}._domainkey.{domain}", "TXT")
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def resolve_domain(domain: str, deep_checks: bool = True) -> DnsLookupOutcome:
    """Resolve MX (falling back to A) for a domain, with caching + retries."""
    cache_key = f"{domain}|{deep_checks}"
    cached = _dns_cache.get(cache_key)
    if cached is not None:
        outcome = cached
        outcome.from_cache = True
        return outcome

    resolver = _build_resolver()
    start = time.perf_counter()
    outcome = DnsLookupOutcome()

    try:
        mx_answers = _query_with_retry(resolver, domain, "MX")
        mx_records = sorted(
            [(r.preference, str(r.exchange).rstrip(".")) for r in mx_answers],
            key=lambda x: x[0],
        )
        outcome.mx_hosts = [host for _, host in mx_records]
        outcome.mx_exists = len(outcome.mx_hosts) > 0
        outcome.domain_exists = True
        outcome.status = DnsStatus.RESOLVED
        if outcome.mx_hosts:
            outcome.mx_provider = lookup_mx_provider(outcome.mx_hosts[0])
    except dns.resolver.NXDOMAIN:
        outcome.status = DnsStatus.NXDOMAIN
        outcome.domain_exists = False
    except dns.resolver.NoAnswer:
        # No MX record -> try A record fallback (domain may still exist)
        try:
            a_answers = _query_with_retry(resolver, domain, "A")
            if len(list(a_answers)) > 0:
                outcome.domain_exists = True
                outcome.used_a_fallback = True
                outcome.mx_exists = False
                outcome.status = DnsStatus.NO_MX_HAS_A
        except dns.resolver.NXDOMAIN:
            outcome.status = DnsStatus.NXDOMAIN
        except dns.exception.Timeout:
            outcome.status = DnsStatus.TIMEOUT
        except Exception as exc:  # noqa: BLE001
            outcome.status = DnsStatus.ERROR
            outcome.error = str(exc)
    except dns.exception.Timeout:
        outcome.status = DnsStatus.TIMEOUT
    except dns.resolver.NoNameservers as exc:
        outcome.status = DnsStatus.SERVFAIL
        outcome.error = str(exc)
    except Exception as exc:  # noqa: BLE001
        outcome.status = DnsStatus.ERROR
        outcome.error = str(exc)

    if deep_checks and outcome.domain_exists:
        try:
            outcome.has_spf, outcome.has_dmarc = _check_spf_dmarc(resolver, domain)
            outcome.has_dkim_indicator = _check_dkim_indicator(resolver, domain)
        except Exception as exc:  # noqa: BLE001
            logger.debug("SPF/DMARC/DKIM probe failed for %s: %s", domain, exc)

    outcome.response_time_ms = round((time.perf_counter() - start) * 1000, 2)
    _dns_cache.set(cache_key, outcome)
    return outcome


def cache_stats() -> dict:
    return _dns_cache.stats()


def clear_cache() -> None:
    _dns_cache.clear()
