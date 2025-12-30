from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urljoin

import requests
from requests import Response
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)
import structlog


logger = structlog.get_logger(__name__)


class ApiError(Exception):
    pass


class ApiRateLimitError(ApiError):
    pass


class ClinicalConductorClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        if not base_url.endswith("/"):
            # base_url from env may not end with slash; urljoin handles but keep consistent
            base_url = base_url
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"X-ApiKey": api_key})
        self.timeout = timeout_seconds
        self.max_retries = max_retries

    def _full_url(self, endpoint: str) -> str:
        # Accept endpoints that may start with "/" or not
        return urljoin(self.base_url.rstrip("/" ) + "/", endpoint.lstrip("/"))

    def _should_retry(self, resp: Optional[Response], exc: Optional[Exception]) -> bool:
        if exc is not None:
            # Connection errors, timeouts, etc.
            return True
        if resp is None:
            return False
        if resp.status_code in (429, 500, 502, 503, 504):
            return True
        return False

    def _respect_retry_after(self, resp: Response) -> None:
        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    delay = int(ra)
                    logger.warning("rate_limited_retry_after", seconds=delay)
                    time.sleep(delay)
                except ValueError:
                    # ignore malformed header; fall back to exponential backoff
                    pass

    def _request_once(self, method: str, endpoint: str, **kwargs: Any) -> Response:
        url = self._full_url(endpoint)
        resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        if resp.status_code == 429:
            self._respect_retry_after(resp)
        if resp.status_code >= 400:
            # Raise for status for non-2xx
            try:
                resp.raise_for_status()
            except requests.HTTPError as e:
                if resp.status_code == 429:
                    raise ApiRateLimitError(str(e))
                raise
        return resp

    def _retry_wrap(self, func, *args, **kwargs) -> Response:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=0.5, max=8.0),
            retry=retry_if_exception_type((requests.RequestException, ApiRateLimitError)),
        )
        def _inner():
            try:
                return func(*args, **kwargs)
            except requests.HTTPError as e:
                resp = getattr(e, "response", None)
                if resp is not None and resp.status_code in (429, 500, 502, 503, 504):
                    # Convert to retryable error
                    raise ApiRateLimitError(str(e))
                raise

        return _inner()

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Response:
        return self._retry_wrap(self._request_once, method, endpoint, **kwargs)

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.debug("api_get", endpoint=endpoint, params=params)
        resp = self._request("GET", endpoint, params=params or {})
        return self._parse_json(resp)

    def get_with_parameters(self, endpoint: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return self.get(endpoint, params=parameters)

    def get_odata(
        self,
        endpoint: str,
        filter: Optional[str] = None,
        top: int = 1000,
        orderby: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch OData collections with pagination.

        Supports both $skip-based and @odata.nextLink pagination styles.
        """
        results: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {"$top": top, "$skip": 0}
        if filter:
            params["$filter"] = filter
        if orderby:
            params["$orderby"] = orderby

        next_url: Optional[str] = None
        while True:
            if next_url:
                # next_url may be absolute; call session directly
                resp = self.session.get(next_url, timeout=self.timeout)
                if resp.status_code == 429:
                    self._respect_retry_after(resp)
                if resp.status_code >= 400:
                    try:
                        resp.raise_for_status()
                    except requests.HTTPError as e:
                        if resp.status_code in (429, 500, 502, 503, 504):
                            # Retry this iteration via wrapper
                            resp = self._retry_wrap(self.session.get, next_url, timeout=self.timeout)
                        else:
                            raise
            else:
                resp = self._request("GET", endpoint, params=params)

            data = self._parse_json(resp)
            values = data.get("value")
            if isinstance(values, list):
                results.extend(values)
                if "@odata.nextLink" in data and data["@odata.nextLink"]:
                    next_url = data["@odata.nextLink"]
                    continue
                # Fallback to $skip paging when no nextLink and page is full
                if len(values) == top:
                    params["$skip"] = params.get("$skip", 0) + top
                    next_url = None
                    continue
                break
            else:
                # Some endpoints may return dicts (single resource)
                results.append(data)
                break

        return results

    def get_paginated(self, endpoint: str, page_size: int = 1000) -> Iterator[Dict[str, Any]]:
        """Yield records page by page from an OData endpoint."""
        skip = 0
        while True:
            page = self.get(endpoint, params={"$top": page_size, "$skip": skip})
            values = page.get("value", [])
            if not values:
                break
            for row in values:
                yield row
            if len(values) < page_size:
                break
            skip += page_size

    @staticmethod
    def _parse_json(resp: Response) -> Dict[str, Any]:
        try:
            return resp.json()
        except ValueError as e:
            raise ApiError(f"Invalid JSON response: {e}")
