from __future__ import annotations

import time

import pytest
import responses

from src.api.client import ClinicalConductorClient, ApiRateLimitError


BASE = "https://example.com/CCSWEB"
API_KEY = "test-key"


@responses.activate
def test_get_simple_success():
    client = ClinicalConductorClient(BASE, API_KEY, timeout_seconds=2, max_retries=2)
    responses.add(
        responses.GET,
        f"{BASE}/v1/things",
        json={"value": [{"id": 1}, {"id": 2}]},
        status=200,
    )
    data = client.get("/v1/things")
    assert data["value"][0]["id"] == 1


@responses.activate
def test_get_odata_pagination_by_skip():
    client = ClinicalConductorClient(BASE, API_KEY, timeout_seconds=2, max_retries=2)
    # First page
    responses.add(
        responses.GET,
        f"{BASE}/v1/records",
        match=[responses.matchers.query_param_matcher({"$top": "2", "$skip": "0"})],
        json={"value": [{"id": 1}, {"id": 2}]},
        status=200,
    )
    # Second page (no next link, full page -> skip)
    responses.add(
        responses.GET,
        f"{BASE}/v1/records",
        match=[responses.matchers.query_param_matcher({"$top": "2", "$skip": "2"})],
        json={"value": [{"id": 3}]},
        status=200,
    )
    out = client.get_odata("/v1/records", top=2)
    assert [r["id"] for r in out] == [1, 2, 3]


@responses.activate
def test_retry_on_429_with_retry_after():
    client = ClinicalConductorClient(BASE, API_KEY, timeout_seconds=2, max_retries=3)

    responses.add(
        responses.GET,
        f"{BASE}/v1/rate-limited",
        status=429,
        headers={"Retry-After": "1"},
    )
    responses.add(
        responses.GET,
        f"{BASE}/v1/rate-limited",
        json={"value": []},
        status=200,
    )
    t0 = time.time()
    data = client.get("/v1/rate-limited")
    assert data["value"] == []
    assert time.time() - t0 >= 1.0  # honored Retry-After


@responses.activate
def test_404_raises():
    client = ClinicalConductorClient(BASE, API_KEY, timeout_seconds=2, max_retries=1)
    responses.add(
        responses.GET,
        f"{BASE}/v1/missing",
        status=404,
    )
    with pytest.raises(Exception):
        client.get("/v1/missing")


@responses.activate
def test_retry_on_server_error_then_success():
    client = ClinicalConductorClient(BASE, API_KEY, timeout_seconds=2, max_retries=3)
    responses.add(
        responses.GET,
        f"{BASE}/v1/flaky",
        status=503,
    )
    responses.add(
        responses.GET,
        f"{BASE}/v1/flaky",
        json={"value": [{"id": 1}]},
        status=200,
    )
    data = client.get("/v1/flaky")
    assert data["value"][0]["id"] == 1
