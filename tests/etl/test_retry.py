import time
import types
import pytest

from src.etl.errors import TransientError, PermanentError
from src.etl.retry import run_with_retry, classify_exception


def test_run_with_retry_transient_succeeds(monkeypatch):
    attempts = {"n": 0}

    def flakey():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TransientError("temp fail")
        return "ok"

    start = time.time()
    result = run_with_retry(flakey)
    end = time.time()

    assert result == "ok"
    assert attempts["n"] == 3
    assert end >= start


def test_run_with_retry_permanent_raises():
    def bad():
        raise PermanentError("no retry")

    with pytest.raises(PermanentError):
        run_with_retry(bad)


def test_classify_exception():
    assert classify_exception(TransientError()) == "transient"
    assert classify_exception(PermanentError()) == "permanent"
