"""Tests for database module."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import psycopg2

from src.config import reload_settings
from src.db import DataLoader, LoadResult, get_pool


class TestConnectionPool:
    """Tests for connection pool."""

    def setup_method(self):
        """Set up test environment."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/test_db"
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        os.environ["CC_API_KEY"] = "test-key"
        os.environ["ENVIRONMENT"] = "test"
        os.environ["DRY_RUN"] = "false"
        reload_settings()

    def test_pool_initialization(self):
        """Test pool initialization."""
        pool = get_pool()
        assert pool is not None
        assert pool.database_url == "postgresql://user:pass@localhost:5432/test_db"

    def teardown_method(self):
        """Clean up test environment."""
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("CC_API_BASE_URL", None)
        os.environ.pop("CC_API_KEY", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DRY_RUN", None)


class TestDataLoader:
    """Tests for DataLoader."""

    def setup_method(self):
        """Set up test environment."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/test_db"
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        os.environ["CC_API_KEY"] = "test-key"
        os.environ["ENVIRONMENT"] = "test"
        os.environ["DRY_RUN"] = "false"
        reload_settings()

    def test_prepare_records(self):
        """Test record preparation."""
        loader = DataLoader()
        records = [
            {"data": {"id": "123", "name": "Test"}},
            {"data": {"id": "456", "name": "Test2"}},
        ]

        prepared = loader._prepare_records(
            records=records,
            etl_job_id=1,
            etl_run_id=1,
            source_id_key="id",
        )

        assert len(prepared) == 2
        assert prepared[0]["source_id"] == "123"
        assert prepared[1]["source_id"] == "456"
        assert all("etl_job_id" in r for r in prepared)
        assert all("etl_run_id" in r for r in prepared)

    def test_prepare_records_missing_data(self):
        """Test record preparation with missing data."""
        loader = DataLoader()
        records = [{"id": "123"}]  # Missing 'data' field

        with pytest.raises(ValueError, match="missing 'data' field"):
            loader._prepare_records(
                records=records,
                etl_job_id=1,
                etl_run_id=1,
                source_id_key="id",
            )

    def test_prepare_records_missing_source_id(self):
        """Test record preparation with missing source_id."""
        loader = DataLoader()
        records = [{"data": {"name": "Test"}}]  # Missing 'id' field

        with pytest.raises(ValueError, match="missing source_id"):
            loader._prepare_records(
                records=records,
                etl_job_id=1,
                etl_run_id=1,
                source_id_key="id",
            )

    def test_deduplicate_records(self):
        """Test record deduplication."""
        loader = DataLoader()
        records = [
            {"source_id": "123", "data": '{"name": "First"}'},
            {"source_id": "456", "data": '{"name": "Second"}'},
            {"source_id": "123", "data": '{"name": "Last"}'},  # Duplicate
        ]

        deduplicated = loader._deduplicate_records(records)

        assert len(deduplicated) == 2
        # Last occurrence should win
        assert deduplicated[0]["source_id"] == "456"
        assert deduplicated[1]["source_id"] == "123"
        assert deduplicated[1]["data"] == '{"name": "Last"}'

    def test_load_to_staging_empty_records(self):
        """Test loading empty records."""
        loader = DataLoader()

        result = loader.load_to_staging(
            table_name="test_staging",
            records=[],
            etl_job_id=1,
            etl_run_id=1,
        )

        assert result.rows_inserted == 0
        assert result.rows_updated == 0
        assert result.batches_total == 0

    @patch("src.db.loader.get_pool")
    def test_load_to_staging_dry_run(self, mock_pool):
        """Test loading in dry run mode."""
        os.environ["DRY_RUN"] = "true"
        reload_settings()

        loader = DataLoader()

        with pytest.raises(Exception, match="Database writes are disabled"):
            loader.load_to_staging(
                table_name="test_staging",
                records=[{"data": {"id": "123"}}],
                etl_job_id=1,
                etl_run_id=1,
            )

    def teardown_method(self):
        """Clean up test environment."""
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("CC_API_BASE_URL", None)
        os.environ.pop("CC_API_KEY", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DRY_RUN", None)

