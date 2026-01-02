"""Preflight safety checks before network or database operations.

Enforces guardrails to prevent accidental production operations
in development/test environments.
"""

from typing import Optional

from src.config.settings import get_settings


class PreflightError(Exception):
    """Raised when preflight check fails."""

    pass


def check_environment() -> None:
    """Check that environment is properly configured.

    Raises:
        PreflightError: If environment check fails.
    """
    settings = get_settings()

    if settings.is_development or settings.is_test:
        if not settings.dry_run:
            raise PreflightError(
                f"DRY_RUN must be true in {settings.environment} environment. "
                "Set DRY_RUN=true or ENVIRONMENT=production to proceed."
            )


def check_api_host() -> None:
    """Check that API host is safe for current environment.

    Prevents calling production API in development/test.

    Raises:
        PreflightError: If API host is not allowed for current environment.
    """
    settings = get_settings()
    api_url = settings.api.base_url.lower()

    # Production API host (blocked in dev/test)
    production_hosts = [
        "tektonresearch.clinicalconductor.com",
        "tektonresearch.clinicalconductor.com/ccsweb",
    ]

    if settings.is_development or settings.is_test:
        for host in production_hosts:
            if host in api_url:
                raise PreflightError(
                    f"Cannot call production API ({host}) in {settings.environment} environment. "
                    "Use a test/staging API URL or set ENVIRONMENT=production."
                )


def check_database_write(dry_run: Optional[bool] = None) -> None:
    """Check if database writes are allowed.

    Args:
        dry_run: Optional override for dry_run setting. If None, uses global setting.

    Raises:
        PreflightError: If database writes are not allowed.
    """
    settings = get_settings()
    
    # Use provided dry_run parameter, or fall back to global setting
    is_dry_run = dry_run if dry_run is not None else settings.dry_run

    if is_dry_run:
        raise PreflightError(
            "Database writes are disabled in DRY_RUN mode. "
            "Set DRY_RUN=false to enable writes."
        )


def check_network_request(dry_run: Optional[bool] = None) -> None:
    """Check if network requests are allowed.

    Args:
        dry_run: Optional override for dry_run setting. If None, uses global setting.

    Raises:
        PreflightError: If network requests are not allowed.
    """
    settings = get_settings()
    
    # Use provided dry_run parameter, or fall back to global setting
    is_dry_run = dry_run if dry_run is not None else settings.dry_run

    if is_dry_run:
        raise PreflightError(
            "Network requests are disabled in DRY_RUN mode. "
            "Set DRY_RUN=false to enable network requests."
        )


def preflight_check(
    allow_db_write: bool = False,
    allow_network: bool = False,
    dry_run: Optional[bool] = None,
) -> None:
    """Run all preflight checks before an operation.

    Args:
        allow_db_write: If True, allows database writes (checks DRY_RUN).
        allow_network: If True, allows network requests (checks DRY_RUN and API host).
        dry_run: Optional override for dry_run setting. If None, uses global setting.

    Raises:
        PreflightError: If any check fails.
    """
    check_environment()

    if allow_network:
        check_api_host()
        check_network_request(dry_run=dry_run)

    if allow_db_write:
        check_database_write(dry_run=dry_run)


def require_production() -> None:
    """Require production environment for sensitive operations.

    Raises:
        PreflightError: If not in production environment.
    """
    settings = get_settings()

    if not settings.is_production:
        raise PreflightError(
            f"This operation requires production environment. "
            f"Current environment: {settings.environment}"
        )


def get_dry_run_status() -> tuple[bool, Optional[str]]:
    """Get dry run status and reason.

    Returns:
        Tuple of (is_dry_run, reason_if_dry_run).
    """
    settings = get_settings()

    if settings.dry_run:
        reason = f"DRY_RUN=true in {settings.environment} environment"
        return (True, reason)

    return (False, None)

