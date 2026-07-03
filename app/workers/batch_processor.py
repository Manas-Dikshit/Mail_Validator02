from __future__ import annotations

import logging
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from app.config.settings import get_settings
from app.models.schemas import EmailValidationResult, ValidationJobSummary
from app.services.validation_service import validate_single_email

logger = logging.getLogger(__name__)
settings = get_settings()

ProgressCallback = Callable[[int, int], None]


def process_emails_batch(
    emails: list[str],
    *,
    check_dns: bool = True,
    deep_dns_checks: bool = True,
    max_workers: Optional[int] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> tuple[list[EmailValidationResult], ValidationJobSummary]:
    """Validate a list of emails concurrently. DNS lookups are I/O bound so a
    thread pool (not a process pool) is the right primitive here.

    Duplicate emails (case-insensitive, normalized) are validated once and
    the result is reused for all occurrences to avoid redundant DNS work.
    """
    start = time.perf_counter()
    total = len(emails)
    workers = max_workers or settings.dns_thread_pool_workers

    normalized_keys = [e.strip().lower() for e in emails]
    key_counts = Counter(normalized_keys)
    unique_keys = list(dict.fromkeys(normalized_keys))  # preserve first-seen order

    key_to_original: dict[str, str] = {}
    for original, key in zip(emails, normalized_keys):
        key_to_original.setdefault(key, original)

    results_by_key: dict[str, EmailValidationResult] = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_key = {
            executor.submit(
                validate_single_email,
                key_to_original[key],
                check_dns=check_dns,
                deep_dns_checks=deep_dns_checks,
            ): key
            for key in unique_keys
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Validation failed for %s", key)
                result = EmailValidationResult(
                    original_email=key_to_original[key],
                    reason=f"Internal error during validation: {exc}",
                )
            result.duplicate_count = key_counts[key]
            results_by_key[key] = result
            completed += 1
            if progress_callback:
                progress_callback(completed, len(unique_keys))

    # Re-expand to original row order / cardinality
    ordered_results = [results_by_key[key] for key in normalized_keys]

    valid = sum(
        1 for r in ordered_results if str(r.validation_status.value).startswith("VALID")
    )
    invalid = sum(
        1 for r in ordered_results if str(r.validation_status.value).startswith("INVALID")
    )
    unknown = total - valid - invalid
    duplicates = sum(1 for k in normalized_keys if key_counts[k] > 1)

    summary = ValidationJobSummary(
        total_rows=total,
        processed_rows=len(ordered_results),
        valid_count=valid,
        invalid_count=invalid,
        unknown_count=unknown,
        duplicate_count=duplicates,
        elapsed_seconds=round(time.perf_counter() - start, 3),
    )
    return ordered_results, summary
