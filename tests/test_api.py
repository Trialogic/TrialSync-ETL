"""Tests for API client module."""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api import (
    AuthenticationError,
    ClinicalConductorClient,
    NotFoundError,
    ODataParams,
    RateLimitError,
    ServerError,
)
from src.config import reload_settings


class TestODataParams:
    """Tests for ODataParams."""

    def test_to_query_string(self):
        """Test query string generation."""
        params = ODataParams(top=100, skip=0, filter="name eq 'test'")
        query = params.to_query_string()
        assert "$top=100" in query
        assert "$skip=0" in query
        assert "$filter" in query

    def test_to_query_string_empty(self):
        """Test empty query string."""
        params = ODataParams()
        query = params.to_query_string()
        assert query == ""


class TestClinicalConductorClient:
    """Tests for ClinicalConductorClient."""

    def setup_method(self):
        """Set up test environment."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/test_db"
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        os.environ["CC_API_KEY"] = "test-key"
        os.environ["ENVIRONMENT"] = "test"
        os.environ["DRY_RUN"] = "false"
        reload_settings()

    def test_init(self):
        """Test client initialization."""
        client = ClinicalConductorClient()
        assert client.base_url == "https://test-api.example.com"
        assert client.api_key == "test-key"
        assert client.default_top == 100

    def test_init_missing_api_key(self):
        """Test initialization with missing API key."""
        os.environ.pop("CC_API_KEY", None)
        reload_settings()

        with pytest.raises(ValueError, match="API key is required"):
            ClinicalConductorClient()

    def test_init_invalid_base_url(self):
        """Test initialization with invalid base URL."""
        with pytest.raises(ValueError, match="Base URL must use HTTPS"):
            ClinicalConductorClient(base_url="http://insecure.example.com")

    @patch("src.api.client.requests.Session")
    def test_get_odata_single_page(self, mock_session_class):
        """Test getting OData with single page."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "value": [{"id": "1", "name": "Test"}],
            "@odata.count": 1,
        }

        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        client = ClinicalConductorClient()
        pages = list(client.get_odata("/api/v1/studies/odata", page_mode="iterator"))

        assert len(pages) == 1
        assert len(pages[0].items) == 1
        assert pages[0].items[0]["id"] == "1"

    @patch("src.api.client.requests.Session")
    def test_get_odata_multiple_pages(self, mock_session_class):
        """Test getting OData with multiple pages."""
        # Mock responses
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.headers = {"Content-Type": "application/json"}
        mock_response1.json.return_value = {
            "value": [{"id": "1"}],
            "@odata.nextLink": "https://test-api.example.com/api/v1/studies/odata?$skip=1",
        }

        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.headers = {"Content-Type": "application/json"}
        mock_response2.json.return_value = {
            "value": [{"id": "2"}],
        }

        mock_session = MagicMock()
        mock_session.request.side_effect = [mock_response1, mock_response2]
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        client = ClinicalConductorClient()
        pages = list(client.get_odata("/api/v1/studies/odata", page_mode="iterator"))

        assert len(pages) == 2
        assert len(pages[0].items) == 1
        assert len(pages[1].items) == 1

    @patch("src.api.client.requests.Session")
    def test_get_odata_aggregate_mode(self, mock_session_class):
        """Test getting OData in aggregate mode."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "value": [{"id": "1"}, {"id": "2"}],
        }

        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        client = ClinicalConductorClient()
        items = client.get_odata("/api/v1/studies/odata", page_mode="aggregate")

        assert isinstance(items, list)
        assert len(items) == 2

    @patch("src.api.client.requests.Session")
    def test_get_odata_authentication_error(self, mock_session_class):
        """Test handling authentication error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        client = ClinicalConductorClient()

        with pytest.raises(AuthenticationError):
            list(client.get_odata("/api/v1/studies/odata"))

    @patch("src.api.client.requests.Session")
    def test_get_odata_not_found_error(self, mock_session_class):
        """Test handling not found error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        client = ClinicalConductorClient()

        with pytest.raises(NotFoundError):
            list(client.get_odata("/api/v1/nonexistent/odata"))

    @patch("src.api.client.requests.Session")
    def test_get_odata_rate_limit_error(self, mock_session_class):
        """Test handling rate limit error."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        client = ClinicalConductorClient()

        with pytest.raises(RateLimitError):
            list(client.get_odata("/api/v1/studies/odata"))

    @patch("src.api.client.requests.Session")
    def test_get_odata_server_error(self, mock_session_class):
        """Test handling server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        client = ClinicalConductorClient()

        with pytest.raises(ServerError):
            list(client.get_odata("/api/v1/studies/odata"))

    def teardown_method(self):
        """Clean up test environment."""
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("CC_API_BASE_URL", None)
        os.environ.pop("CC_API_KEY", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DRY_RUN", None)

