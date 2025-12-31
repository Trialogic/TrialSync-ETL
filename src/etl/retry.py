import os
import logging
from typing import Callable, Any

import structlog

try:
    import psycopg2
    from psycopg2 import OperationalError
except Exception:  # pragma: no cover
    psycopg2 = None
    OperationalError = Exception

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception,
    before_sleep_log,
)

from .errors import TransientError, PermanentError

logger = structlog.get_logger(__name__)

MAX_RETRIES = int(os.getenv("ETL_MAX_RETRIES", "3"))
BASE_DELAY = float(os.getenv("ETL_RETRY_DELAY_SECONDS", "5"))

TRANSIENT_HTTP = {429, 500, 502, 503, 504}


def _is_transient_exception(exc: BaseException) -> bool:
    # Explicit signal
    if isinstance(exc, TransientError):
        return True

    # Requests-level errors
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        try:
            status = exc.response.status_code  # type: ignore[attr-defined]
        except Exception:
            status = None
        return bool(status in TRANSIENT_HTTP)

    # DB-level errors
    if psycopg2 is not None:
        if isinstance(exc, OperationalError):
            return True
        # psycopg2 specific errors (deadlock, serialization)
        pgcode = getattr(exc, "pgcode", None)
        if pgcode in {"40P01", "40001"}:  # deadlock_detected, serialization_failure
            return True

    return False


def _retry_predicate(exc: BaseException) -> bool:
    return _is_transient_exception(exc)


def _stop() -> Any:
    return stop_after_attempt(MAX_RETRIES)


def _wait() -> Any:
    # random exponential backoff with cap
    return wait_random_exponential(multiplier=BASE_DELAY, max=60)


def run_with_retry(func: Callable, *args, **kwargs):
    """Run a callable with standardized retry/backoff for transient errors."""

    @retry(
        retry=retry_if_exception(_retry_predicate),
        stop=_stop(),
        wait=_wait(),
        reraise=True,
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    def _wrapped():
        return func(*args, **kwargs)

    return _wrapped()


def classify_exception(exc: BaseException) -> str:
    """Return 'transient' or 'permanent' for logging/metrics."""
    return "transient" if _is_transient_exception(exc) else "permanent"
