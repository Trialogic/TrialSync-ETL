"""Clinical Conductor API client.

Provides authenticated, paginated access to Clinical Conductor OData endpoints
with rate limiting, retries, and error handling.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Any, Generator, Optional, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings, preflight_check
from src.metrics import get_metrics_collector

logger = structlog.get_logger(__name__)


@dataclass
class ODataParams:
    """OData query parameters."""

    top: Optional[int] = None
    skip: Optional[int] = None
    filter: Optional[str] = None
    orderby: Optional[str] = None

    def to_query_string(self) -> str:
        """Convert to OData query string.

        Returns:
            URL-encoded query string (e.g., '$top=100&$skip=0').
        """
        params = {}
        if self.top is not None:
            params["$top"] = self.top
        if self.skip is not None:
            params["$skip"] = self.skip
        if self.filter is not None:
            params["$filter"] = self.filter
        if self.orderby is not None:
            params["$orderby"] = self.orderby
        return urlencode(params)


@dataclass
class Page:
    """A paginated page of results."""

    items: list[dict[str, Any]]
    count: Optional[int] = None
    next_link: Optional[str] = None
    page_index: int = 0


class APIError(Exception):
    """Base exception for API errors."""

    pass


class AuthenticationError(APIError):
    """Authentication failed (401/403)."""

    pass


class NotFoundError(APIError):
    """Resource not found (404)."""

    pass


class RateLimitError(APIError):
    """Rate limit exceeded (429)."""

    pass


class ServerError(APIError):
    """Server error (5xx)."""

    pass


class ClientError(APIError):
    """Client error (4xx, excluding 401/403/404/429)."""

    pass


class TimeoutError(APIError):
    """Request timeout."""

    pass


class NetworkError(APIError):
    """Network/connection error."""

    pass


class ParseError(APIError):
    """Response parsing error."""

    pass


class ValidationError(APIError):
    """Response validation error."""

    pass


class PaginationLimitExceeded(APIError):
    """Pagination limit exceeded."""

    pass


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate_per_second: float):
        """Initialize rate limiter.

        Args:
            rate_per_second: Maximum requests per second.
        """
        self.rate = rate_per_second
        self.tokens = rate_per_second
        self.last_update = time.time()

    def acquire(self) -> None:
        """Acquire a token, blocking if necessary."""
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        self.tokens = min(
            self.rate, self.tokens + elapsed * self.rate
        )
        self.last_update = now

        # Wait if no tokens available
        if self.tokens < 1.0:
            wait_time = (1.0 - self.tokens) / self.rate
            time.sleep(wait_time)
            self.tokens = 0.0
        else:
            self.tokens -= 1.0


class ClinicalConductorClient:
    """Client for Clinical Conductor API.

    Provides authenticated access to OData endpoints with pagination,
    rate limiting, retries, and error handling.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        rate_limit_rps: Optional[float] = None,
        default_top: int = 100,
        max_pages: int = 10000,
        max_records: Optional[int] = None,
        strict_validation: bool = False,
    ):
        """Initialize client.

        Args:
            base_url: API base URL. If None, uses settings.
            api_key: API key. If None, uses settings.
            timeout: Request timeout in milliseconds. If None, uses settings.
            max_retries: Maximum retries. If None, uses settings.
            rate_limit_rps: Rate limit (requests per second). If None, uses settings.
            default_top: Default $top value for pagination.
            max_pages: Maximum pages to fetch before raising PaginationLimitExceeded.
            max_records: Maximum records to fetch (optional).
            strict_validation: Enable strict response validation.
        """
        settings = get_settings()

        self.base_url = (base_url or settings.api.base_url).rstrip("/")
        self.api_key = api_key or settings.api.key
        self.timeout_ms = timeout or settings.api.timeout
        self.timeout_seconds = self.timeout_ms / 1000.0
        # Validate and set max_retries
        max_retries_val = max_retries or settings.api.max_retries
        if not isinstance(max_retries_val, int):
            raise ValueError(f"max_retries must be an integer, got {type(max_retries_val)}")
        self.max_retries = max_retries_val
        
        self.rate_limit_rps = rate_limit_rps or settings.api.rate_limit_per_second
        self.default_top = default_top
        
        # Validate and set max_pages
        if not isinstance(max_pages, int):
            raise ValueError(f"max_pages must be an integer, got {type(max_pages)}")
        self.max_pages = max_pages
        
        # Validate and set max_records
        if max_records is not None and not isinstance(max_records, int):
            raise ValueError(f"max_records must be an integer or None, got {type(max_records)}")
        self.max_records = max_records
        
        self.strict_validation = strict_validation

        # Validate configuration
        if not self.api_key:
            raise ValueError("API key is required")

        if not self.base_url.startswith("https://"):
            raise ValueError("Base URL must use HTTPS")

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(self.rate_limit_rps)

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "CCAPIKey": self.api_key,
            }
        )

    def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[dict[str, Any]] = None,
        dry_run: Optional[bool] = None,
    ) -> requests.Response:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Full URL to request.
            params: Query parameters.

        Returns:
            Response object.

        Raises:
            APIError: On various error conditions.
        """
        request_id = str(uuid.uuid4())

        @retry(
            retry=retry_if_exception_type((RateLimitError, ServerError, TimeoutError, NetworkError)),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=60),
            reraise=True,
        )
        def _do_request() -> requests.Response:
            # Rate limiting
            self.rate_limiter.acquire()

            # Preflight check
            preflight_check(allow_network=True, dry_run=dry_run)

            start_time = time.time()

            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    timeout=self.timeout_seconds,
                )

                duration_ms = (time.time() - start_time) * 1000
                duration_seconds = duration_ms / 1000.0

                # Extract route from URL for metrics (remove base URL and query params)
                route = url.replace(self.base_url, "").split("?")[0] or "/"

                # Record metrics
                metrics_collector = get_metrics_collector()
                metrics_collector.record_api_request(
                    route=route,
                    method=method,
                    status_code=response.status_code,
                    duration_seconds=duration_seconds,
                )

                # Log request
                logger.info(
                    "api_request",
                    request_id=request_id,
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )

                # Handle response
                self._handle_response(response, request_id)

                return response

            except requests.exceptions.Timeout as e:
                duration_ms = (time.time() - start_time) * 1000
                duration_seconds = duration_ms / 1000.0

                # Extract route from URL for metrics
                route = url.replace(self.base_url, "").split("?")[0] or "/"

                # Record metrics (timeout = 408)
                metrics_collector = get_metrics_collector()
                metrics_collector.record_api_request(
                    route=route,
                    method=method,
                    status_code=408,
                    duration_seconds=duration_seconds,
                )

                logger.warning(
                    "api_request_timeout",
                    request_id=request_id,
                    url=url,
                    duration_ms=duration_ms,
                )
                raise TimeoutError(f"Request timeout: {e}") from e

            except requests.exceptions.ConnectionError as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    "api_request_network_error",
                    request_id=request_id,
                    url=url,
                    duration_ms=duration_ms,
                )
                raise NetworkError(f"Network error: {e}") from e

            except requests.exceptions.RequestException as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    "api_request_error",
                    request_id=request_id,
                    url=url,
                    error=str(e),
                    duration_ms=duration_ms,
                )
                raise APIError(f"Request failed: {e}") from e

        return _do_request()

    def _handle_response(
        self, response: requests.Response, request_id: str
    ) -> None:
        """Handle HTTP response errors.

        Args:
            response: Response object.
            request_id: Request ID for logging.

        Raises:
            APIError: On error status codes.
        """
        status = response.status_code

        if status == 200:
            return

        # Check for Retry-After header (429)
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    wait_seconds = int(retry_after)
                except ValueError:
                    # Try parsing as HTTP-date (simplified)
                    wait_seconds = 60  # Default
                logger.warning(
                    "rate_limit_exceeded",
                    request_id=request_id,
                    retry_after=wait_seconds,
                )
                time.sleep(wait_seconds)
            raise RateLimitError(f"Rate limit exceeded (429)")

        if status == 401 or status == 403:
            raise AuthenticationError(f"Authentication failed ({status})")

        if status == 404:
            raise NotFoundError(f"Resource not found (404)")

        if 400 <= status < 500:
            raise ClientError(f"Client error ({status}): {response.text}")

        if 500 <= status < 600:
            # Don't retry 501 (Not Implemented) or 505 (HTTP Version Not Supported)
            if status in (501, 505):
                raise ServerError(f"Server error ({status}): {response.text}")
            raise ServerError(f"Server error ({status}): {response.text}")

        raise APIError(f"Unexpected status code ({status})")

    def _parse_response(
        self, response: requests.Response, request_id: str
    ) -> dict[str, Any]:
        """Parse JSON response.

        Args:
            response: Response object.
            request_id: Request ID for logging.

        Returns:
            Parsed JSON data.

        Raises:
            ParseError: On JSON parse errors.
            ValidationError: On validation errors.
        """
        # Check Content-Type
        content_type = response.headers.get("Content-Type", "").lower()
        if "application/json" not in content_type:
            raise ParseError(
                f"Expected application/json, got {content_type}"
            )

        try:
            data = response.json()
        except ValueError as e:
            raise ParseError(f"Invalid JSON: {e}") from e

        # Validate OData structure
        if self.strict_validation:
            if not isinstance(data, dict):
                raise ValidationError("Response must be a JSON object")
            if "value" not in data:
                raise ValidationError("Response missing 'value' array")
            if not isinstance(data["value"], list):
                raise ValidationError("Response 'value' must be an array")
        else:
            if not isinstance(data, dict):
                logger.warning(
                    "unexpected_response_format",
                    request_id=request_id,
                    type=type(data).__name__,
                )
            elif "value" not in data and "items" not in data:
                logger.warning(
                    "missing_value_array",
                    request_id=request_id,
                )
            elif "value" in data and not isinstance(data.get("value"), list):
                logger.warning(
                    "value_not_array",
                    request_id=request_id,
                    type=type(data.get("value")).__name__,
                )
            elif "items" in data and not isinstance(data.get("items"), list):
                logger.warning(
                    "items_not_array",
                    request_id=request_id,
                    type=type(data.get("items")).__name__,
                )

        return data

    def get_odata(
        self,
        resource: str,
        params: Optional[ODataParams] = None,
        page_mode: str = "iterator",
        dry_run: Optional[bool] = None,
    ) -> Union[Generator[Page, None, None], list[dict[str, Any]]]:
        """Get OData resource with pagination.

        Args:
            resource: Resource path (e.g., '/api/v1/studies/odata').
            params: OData query parameters.
            page_mode: 'iterator' (yields Page objects) or 'aggregate' (returns all items).

        Yields:
            Page objects (if page_mode='iterator').

        Returns:
            List of all items (if page_mode='aggregate').

        Raises:
            APIError: On various error conditions.
            PaginationLimitExceeded: If max_pages or max_records exceeded.
        """
        if params is None:
            params = ODataParams()

        # Normalize resource path
        if not resource.startswith("/"):
            resource = "/" + resource

        # Set default $top if not provided
        if params.top is None:
            params.top = self.default_top

        skip = params.skip or 0
        page_index = 0
        all_items: list[dict[str, Any]] = []
        total_records = 0
        previous_items_count = None  # Track previous page item count to detect pagination issues

        while True:
            # Check limits - validate types before comparison
            if not isinstance(page_index, int):
                raise TypeError(f"page_index must be an integer, got {type(page_index)}")
            if not isinstance(self.max_pages, int):
                raise TypeError(f"max_pages must be an integer, got {type(self.max_pages)}")
            if page_index >= self.max_pages:
                raise PaginationLimitExceeded(
                    f"Maximum pages ({self.max_pages}) exceeded"
                )

            if self.max_records is not None:
                if not isinstance(total_records, int):
                    raise TypeError(f"total_records must be an integer, got {type(total_records)}")
                if not isinstance(self.max_records, int):
                    raise TypeError(f"max_records must be an integer, got {type(self.max_records)}")
                if total_records >= self.max_records:
                    raise PaginationLimitExceeded(
                        f"Maximum records ({self.max_records}) exceeded"
                    )

            # Build URL
            # Base URL should end with /CCSWEB/ (not /CCSWEB/api/v1)
            # Resource should start with /api/v1/...
            current_params = ODataParams(
                top=params.top,
                skip=skip,
                filter=params.filter,
                orderby=params.orderby,
            )
            query_string = current_params.to_query_string()
            
            # Normalize base URL and resource
            # Base URL may end with /CCSWEB or /CCSWEB/api/v1
            # Resource may start with /api/v1/ or just /
            base = self.base_url.rstrip("/")
            
            # If base ends with /api/v1, remove /api/v1 from resource if present
            if base.endswith("/api/v1"):
                if resource.startswith("/api/v1/"):
                    resource = resource[7:]  # Remove "/api/v1/"
                elif resource.startswith("/api/v1"):
                    resource = resource[6:]  # Remove "/api/v1"
                # base stays as /CCSWEB/api/v1
            else:
                # Base is /CCSWEB, resource should have /api/v1/ prefix
                if not base.endswith("/"):
                    base = base + "/"
            
            # Construct URL
            if not resource.startswith("/"):
                resource = "/" + resource
            url = f"{base}{resource}?{query_string}" if query_string else f"{base}{resource}"

            # Make request
            response = self._make_request("GET", url, dry_run=dry_run)
            data = self._parse_response(response, str(uuid.uuid4()))

            # Extract items - handle multiple response formats:
            # 1. OData format: {"value": [...]}
            # 2. Items format: {"items": [...]}
            # 3. Direct list: [...]
            if isinstance(data, list):
                # Direct list response (non-OData format)
                items = data
                count = None
                next_link = None
            elif isinstance(data, dict):
                # Try OData format first, then items format
                items = data.get("value") or data.get("items", [])
                if not isinstance(items, list):
                    items = []
                count = data.get("@odata.count")
                # Check for both OData and custom next link formats
                next_link = data.get("@odata.nextLink") or data.get("nextPageLink")
            else:
                items = []
                count = None
                next_link = None

            # Update counters
            total_records += len(items)
            page_index += 1

            # Create page
            page = Page(
                items=items,
                count=count,
                next_link=next_link,
                page_index=page_index - 1,
            )

            # Yield or accumulate
            if page_mode == "iterator":
                yield page
            else:
                all_items.extend(items)

            # Check if done
            # For direct list responses (no OData format), stop if we got fewer items than requested
            if not next_link and len(items) < params.top:
                # No more pages - got fewer items than requested
                break

            # If no items returned, we're done
            if not items:
                break
            
            # Detect if API is ignoring pagination (returns same items on every request)
            # This happens when the API doesn't support $skip and returns all results
            if not next_link and previous_items_count is not None:
                if len(items) == previous_items_count and page_index > 1:
                    # Got the same number of items as previous page, API likely ignoring skip
                    # Check if we've already seen these items (simple check: same count and no new unique IDs)
                    if len(items) > 0 and len(all_items) >= len(items):
                        # We've likely seen all items already
                        logger.warning(
                            "api_ignoring_pagination",
                            endpoint=resource,
                            page_index=page_index,
                            items_count=len(items),
                            message="API appears to be ignoring $skip parameter, stopping pagination"
                        )
                        break
            
            previous_items_count = len(items)

            if next_link:
                # Parse next_link to get skip value
                parsed = urlparse(next_link)
                query_params = parse_qs(parsed.query)
                skip_str = query_params.get("$skip", [None])[0]
                if skip_str:
                    try:
                        skip = int(skip_str)
                    except ValueError:
                        # Can't parse skip, increment manually
                        skip += params.top
                else:
                    skip += params.top
            else:
                # No next_link - for direct list responses, we need to be careful
                # If we got exactly params.top items, try one more page to see if there are more
                # But if we've already tried and got 0 items, we're done (handled above)
                # Increment skip for next iteration
                skip += params.top
                
                # Safety: if we got exactly params.top items with no next_link, 
                # and we're on a high page number, log a warning
                if page_index > 100 and len(items) == params.top:
                    logger.warning(
                        "pagination_without_next_link",
                        endpoint=resource,
                        page_index=page_index,
                        total_records=total_records,
                        items_in_page=len(items),
                        skip=skip,
                        message="No next_link provided, continuing pagination based on item count"
                    )

        # Return aggregated results if requested
        if page_mode == "aggregate":
            return all_items

