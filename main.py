#!/usr/bin/env python3
"""
Email Validator CLI

Usage:
    python main.py input.xlsx output.xlsx
    python main.py input.csv output.xlsx
    python main.py input.csv output.xlsx --column "Email Address"
    python main.py input.csv output.xlsx --no-dns
    python main.py input.csv output.xlsx --workers 64
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.utils.logging_config import configure_logging
from app.services.file_service import (
    load_dataframe,
    detect_email_column,
    build_output_dataframe,
    write_output_xlsx,
    NoEmailColumnFoundError,
    MultipleEmailColumnsError,
)
from app.workers.batch_processor import process_emails_batch

configure_logging()
logger = logging.getLogger("email_validator.cli")


def _print_progress(done: int, total: int) -> None:
    width = 40
    filled = int(width * done / max(total, 1))
    bar = "#" * filled + "-" * (width - filled)
    pct = (done / max(total, 1)) * 100
    sys.stdout.write(f"\r[{bar}] {done}/{total} ({pct:5.1f}%)")
    sys.stdout.flush()
    if done == total:
        sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate emails in a CSV/XLSX file.")
    parser.add_argument("input_file", help="Path to input .csv or .xlsx file")
    parser.add_argument("output_file", help="Path to write the output .xlsx file")
    parser.add_argument(
        "--column", default=None, help="Explicit email column name (skip auto-detection)"
    )
    parser.add_argument(
        "--no-dns", action="store_true", help="Skip DNS/MX lookups (syntax-only validation)"
    )
    parser.add_argument(
        "--no-deep-dns",
        action="store_true",
        help="Skip SPF/DMARC/DKIM-indicator lookups (faster, MX-only)",
    )
    parser.add_argument(
        "--workers", type=int, default=None, help="DNS thread pool size (default from config)"
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input_file)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        return 1

    logger.info("Loading %s", input_path)
    try:
        df = load_dataframe(input_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load input file: %s", exc)
        return 1

    try:
        column = detect_email_column(list(df.columns), preferred=args.column)
    except MultipleEmailColumnsError as exc:
        logger.error(
            "Multiple possible email columns found: %s. Re-run with --column <name>.",
            exc.candidates,
        )
        return 1
    except NoEmailColumnFoundError as exc:
        logger.error(str(exc))
        return 1

    logger.info("Using email column: '%s' (%d rows)", column, len(df))

    # Some users paste row-like strings into a single cell, e.g.
    #   email@example.com | Name | https://example.com
    # In that case, validate only the left-most token.
    def _extract_email_cell(value: str) -> str:
        raw = (value or "").strip()
        if "|" in raw:
            raw = raw.split("|", 1)[0].strip()
        return raw

    emails = [
        _extract_email_cell(v) for v in df[column].fillna("").astype(str).tolist()
    ]

    results, summary = process_emails_batch(
        emails,
        check_dns=not args.no_dns,
        deep_dns_checks=not args.no_deep_dns,
        max_workers=args.workers,
        progress_callback=_print_progress,
    )

    output_df = build_output_dataframe(df, column, results)
    output_path = write_output_xlsx(output_df, args.output_file)

    logger.info(
        "Done in %.2fs | total=%d valid=%d invalid=%d unknown=%d duplicates=%d",
        summary.elapsed_seconds,
        summary.total_rows,
        summary.valid_count,
        summary.invalid_count,
        summary.unknown_count,
        summary.duplicate_count,
    )
    logger.info("Output written to: %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
