from typing import Optional

class TransientError(Exception):
    """Errors that may succeed on retry (network blips, DB deadlocks, 429s)."""
    def __init__(self, message: str = "Transient error", *, cause: Optional[BaseException] = None):
        super().__init__(message)
        self.cause = cause

class PermanentError(Exception):
    """Errors that should not be retried (validation, 4xx other than 429)."""
    pass
