from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _load_lines(path: Path) -> frozenset[str]:
    if not path.exists():
        logger.warning("Data file not found: %s", path)
        return frozenset()
    with open(path, "r", encoding="utf-8") as fh:
        return frozenset(
            line.strip().lower() for line in fh if line.strip() and not line.startswith("#")
        )


def _load_json(path: Path) -> dict:
    if not path.exists():
        logger.warning("Data file not found: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def get_disposable_domains() -> frozenset[str]:
    return _load_lines(settings.disposable_domains_file)


@lru_cache
def get_free_providers() -> frozenset[str]:
    return _load_lines(settings.free_providers_file)


@lru_cache
def get_role_based_prefixes() -> frozenset[str]:
    return _load_lines(settings.role_based_prefixes_file)


@lru_cache
def get_reserved_domains() -> frozenset[str]:
    return _load_lines(settings.reserved_domains_file)


@lru_cache
def get_spam_keywords() -> frozenset[str]:
    return _load_lines(settings.spam_keywords_file)


@lru_cache
def get_typo_domain_map() -> dict:
    return _load_json(settings.typo_domains_file)


@lru_cache
def get_mx_provider_map() -> dict:
    return _load_json(settings.mx_provider_map_file)


def add_disposable_domain(domain: str) -> None:
    """Extend the disposable list at runtime (also persists to disk)."""
    domain = domain.strip().lower()
    if not domain:
        return
    with open(settings.disposable_domains_file, "a", encoding="utf-8") as fh:
        fh.write(f"\n{domain}")
    get_disposable_domains.cache_clear()
