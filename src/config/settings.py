from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # Database
    DATABASE_HOST: str = Field(default="localhost")
    DATABASE_PORT: int = Field(default=5432)
    DATABASE_NAME: str = Field(default="trialsync-dev")
    DATABASE_USER: str = Field(default="postgres")
    DATABASE_PASSWORD: str = Field(default="postgres")

    # Clinical Conductor API
    CC_API_BASE_URL: str = Field(..., description="Clinical Conductor base URL")
    CC_API_KEY: str = Field(..., description="Clinical Conductor API key")

    # ETL settings
    ETL_BATCH_SIZE: int = 1000
    ETL_MAX_RETRIES: int = 3
    ETL_RETRY_DELAY_SECONDS: int = 5
    ETL_PARALLEL_JOBS: int = 5
    ETL_TIMEOUT_SECONDS: int = 300

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None

    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    ALERT_EMAIL: Optional[str] = None

    # Optional path to a YAML config that can override/extend env
    CONFIG_YAML: Optional[str] = Field(default="config/settings.yaml")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def load_settings() -> Settings:
    """Load Settings from env (.env) and optionally merge a YAML file for overrides.

    Environment variables always take precedence over YAML values.
    """
    base = Settings()  # loads from env/.env

    yaml_path = base.CONFIG_YAML
    if yaml_path and Path(yaml_path).exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # Merge: YAML -> dict, then override with env already applied in base
        if isinstance(data, dict):
            merged = {**data, **base.dict()}
            return Settings(**merged)

    return base
