"""
Application-wide configuration.

All tunables live here so behaviour can be changed via environment
variables without touching business logic.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMAILVAL_", env_file=".env", extra="ignore")

    # --- General ---
    app_name: str = "Email Validation Service"
    log_level: str = "INFO"
    log_json: bool = False

    # --- Limits (RFC based) ---
    max_email_length: int = 254
    max_local_part_length: int = 64
    max_domain_length: int = 255

    # --- DNS ---
    dns_timeout_seconds: float = 3.0
    dns_lifetime_seconds: float = 5.0
    dns_max_retries: int = 2
    dns_retry_backoff_seconds: float = 0.5
    dns_cache_ttl_seconds: int = 3600
    dns_cache_max_size: int = 50_000
    dns_nameservers: list[str] = Field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    dns_thread_pool_workers: int = 32

    # --- Processing ---
    csv_chunk_size: int = 5_000
    max_upload_rows: int = 500_000

    # --- Data files ---
    disposable_domains_file: Path = DATA_DIR / "disposable_domains.txt"
    free_providers_file: Path = DATA_DIR / "free_providers.txt"
    role_based_prefixes_file: Path = DATA_DIR / "role_based_prefixes.txt"
    reserved_domains_file: Path = DATA_DIR / "reserved_domains.txt"
    spam_keywords_file: Path = DATA_DIR / "spam_keywords.txt"
    typo_domains_file: Path = DATA_DIR / "typo_domain_map.json"
    mx_provider_map_file: Path = DATA_DIR / "mx_provider_map.json"

    # --- Column detection ---
    email_column_candidates: list[str] = Field(
        default_factory=lambda: [
            "email",
            "email address",
            "email_address",
            "email id",
            "email_id",
            "e-mail",
            "emailaddress",
            "e mail",
            "mail",
        ]
    )

    # --- API ---
    max_upload_size_mb: int = 100
    api_cors_origins: list[str] = Field(default_factory=lambda: ["*"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
