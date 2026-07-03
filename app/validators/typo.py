from __future__ import annotations

from app.utils.data_loader import get_typo_domain_map, get_free_providers


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def suggest_domain_correction(domain: str) -> str | None:
    domain = domain.lower()
    typo_map = get_typo_domain_map()

    if domain in typo_map:
        return typo_map[domain]

    free_providers = set(get_free_providers())
    # If it's already a known free provider, do not "correct" it.
    if domain in free_providers:
        return None

    # Fallback: edit-distance against major free providers, only surface a
    # suggestion when it's a *close* miss (distance 1-2) to avoid noisy
    # false positives on legitimate custom domains.
    best_match = None
    best_distance = 3
    for provider in free_providers:
        # cheap length filter before running full edit distance
        if abs(len(provider) - len(domain)) > 2:
            continue
        dist = _levenshtein(domain, provider)
        if dist < best_distance and dist > 0:
            best_distance = dist
            best_match = provider

    return best_match
