"""API module for TrialSync ETL.

Provides Clinical Conductor API client.
"""

from src.api.client import (
    APIError,
    AuthenticationError,
    ClientError,
    ClinicalConductorClient,
    NetworkError,
    NotFoundError,
    ODataParams,
    Page,
    PaginationLimitExceeded,
    ParseError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)

__all__ = [
    "ClinicalConductorClient",
    "ODataParams",
    "Page",
    "APIError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ClientError",
    "TimeoutError",
    "NetworkError",
    "ParseError",
    "ValidationError",
    "PaginationLimitExceeded",
]

