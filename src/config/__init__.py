"""Configuration module for TrialSync ETL.

Provides settings loading and preflight safety checks.
"""

from src.config.preflight import (
    PreflightError,
    check_api_host,
    check_database_write,
    check_environment,
    check_network_request,
    get_dry_run_status,
    preflight_check,
    require_production,
)
from src.config.settings import (
    APISettings,
    DatabaseSettings,
    ETLSettings,
    LoggingSettings,
    Settings,
    get_settings,
    reload_settings,
)

__all__ = [
    # Settings
    "Settings",
    "DatabaseSettings",
    "APISettings",
    "ETLSettings",
    "LoggingSettings",
    "get_settings",
    "reload_settings",
    # Preflight checks
    "PreflightError",
    "preflight_check",
    "check_environment",
    "check_api_host",
    "check_database_write",
    "check_network_request",
    "require_production",
    "get_dry_run_status",
]

