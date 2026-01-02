"""Database module for TrialSync ETL.

Provides connection pooling and data loading capabilities.
"""

from src.db.connection import (
    ConnectionPool,
    close_pool,
    get_pool,
)
from src.db.loader import DataLoader, LoadResult

__all__ = [
    "ConnectionPool",
    "get_pool",
    "close_pool",
    "DataLoader",
    "LoadResult",
]

