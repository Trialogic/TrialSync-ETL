"""Database connection pooling for TrialSync ETL.

Provides connection pool management using psycopg2.
"""

import contextlib
from typing import Generator, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extensions import connection as PgConnection

from src.config import get_settings
from src.metrics import get_metrics_collector


class ConnectionPool:
    """PostgreSQL connection pool manager.

    Uses psycopg2's ThreadedConnectionPool for thread-safe connection management.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        minconn: int = 1,
        maxconn: int = 5,
    ):
        """Initialize connection pool.

        Args:
            database_url: PostgreSQL connection URL. If None, uses settings.
            minconn: Minimum number of connections in pool.
            maxconn: Maximum number of connections in pool.
        """
        settings = get_settings()
        self.database_url = database_url or settings.database.url
        self.minconn = minconn
        self.maxconn = maxconn
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    def initialize(self) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            return

        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=self.minconn,
            maxconn=self.maxconn,
            dsn=self.database_url,
        )

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None

    @contextlib.contextmanager
    def get_connection(self) -> Generator[PgConnection, None, None]:
        """Get a connection from the pool (context manager).

        Yields:
            PostgreSQL connection object.

        Raises:
            RuntimeError: If pool is not initialized.
            psycopg2.pool.PoolError: If no connections available.
        """
        if self._pool is None:
            raise RuntimeError("Connection pool not initialized. Call initialize() first.")

        conn = self._pool.getconn()
        
        # Update pool metrics
        try:
            metrics_collector = get_metrics_collector()
            in_use = len([c for c in self._pool._pool if c])
            pool_size = self.maxconn
            waiters = 0  # psycopg2 doesn't expose waiters directly
            metrics_collector.update_db_pool_metrics(
                component="etl",
                in_use=in_use,
                pool_size=pool_size,
                waiters=waiters,
            )
        except Exception:
            pass  # Don't fail if metrics fail
        
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)
            
            # Update pool metrics after release
            try:
                metrics_collector = get_metrics_collector()
                in_use = len([c for c in self._pool._pool if c])
                pool_size = self.maxconn
                metrics_collector.update_db_pool_metrics(
                    component="etl",
                    in_use=in_use,
                    pool_size=pool_size,
                    waiters=0,
                )
            except Exception:
                pass  # Don't fail if metrics fail

    def get_connection_raw(self) -> PgConnection:
        """Get a connection from the pool (manual management).

        Returns:
            PostgreSQL connection object.

        Raises:
            RuntimeError: If pool is not initialized.
            psycopg2.pool.PoolError: If no connections available.

        Note:
            Caller must call pool.putconn(conn) when done.
        """
        if self._pool is None:
            raise RuntimeError("Connection pool not initialized. Call initialize() first.")

        return self._pool.getconn()

    def put_connection(self, conn: PgConnection) -> None:
        """Return a connection to the pool.

        Args:
            conn: Connection to return.
        """
        if self._pool is not None:
            self._pool.putconn(conn)


# Global connection pool instance
_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    """Get or create global connection pool.

    Returns:
        ConnectionPool instance (singleton pattern).
    """
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool(
            minconn=1,
            maxconn=settings.database.pool_size,
        )
        _pool.initialize()
    return _pool


def close_pool() -> None:
    """Close the global connection pool."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None

