"""Tests for ETL executor module."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.etl import ExecutionResult, JobConfig, JobExecutor
from src.config import reload_settings


class TestJobExecutor:
    """Tests for JobExecutor."""

    def setup_method(self):
        """Set up test environment."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/test_db"
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        os.environ["CC_API_KEY"] = "test-key"
        os.environ["ENVIRONMENT"] = "test"
        os.environ["DRY_RUN"] = "false"
        reload_settings()

    @patch("src.etl.executor.get_pool")
    def test_get_job_config(self, mock_pool):
        """Test loading job configuration."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor

        # Mock query result
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "name": "Test Job",
            "source_endpoint": "/api/v1/studies/odata",
            "target_table": "dim_studies_staging",
            "is_active": True,
            "requires_parameters": False,
            "parameter_source_table": None,
            "parameter_source_column": None,
            "source_instance_id": None,
            "description": "Test job description",
        }

        executor = JobExecutor()
        config = executor.get_job_config(1)

        assert config.id == 1
        assert config.name == "Test Job"
        assert config.source_endpoint == "/api/v1/studies/odata"
        assert config.target_table == "dim_studies_staging"
        assert config.requires_parameters is False

    @patch("src.etl.executor.get_pool")
    def test_get_job_config_not_found(self, mock_pool):
        """Test loading non-existent job."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        executor = JobExecutor()

        with pytest.raises(ValueError, match="not found"):
            executor.get_job_config(999)

    @patch("src.etl.executor.get_pool")
    def test_get_job_config_inactive(self, mock_pool):
        """Test loading inactive job."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {
            "id": 1,
            "name": "Inactive Job",
            "source_endpoint": "/api/v1/studies/odata",
            "target_table": "dim_studies_staging",
            "is_active": False,
            "requires_parameters": False,
            "parameter_source_table": None,
            "parameter_source_column": None,
            "source_instance_id": None,
            "description": None,
        }

        executor = JobExecutor()

        with pytest.raises(ValueError, match="not active"):
            executor.get_job_config(1)

    @patch("src.etl.executor.get_pool")
    def test_create_run(self, mock_pool):
        """Test creating run record."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (123,)

        executor = JobExecutor()
        run_id = executor.create_run(job_id=1, parameters={"studyId": 123})

        assert run_id == 123
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("src.etl.executor.get_pool")
    def test_substitute_parameters(self, mock_pool):
        """Test parameter substitution."""
        executor = JobExecutor()

        endpoint = "/api/v1/studies/{studyId}/subjects/odata"
        parameters = {"studyId": 123}

        result = executor.substitute_parameters(endpoint, parameters)

        assert result == "/api/v1/studies/123/subjects/odata"
        assert "{studyId}" not in result

    @patch("src.etl.executor.get_pool")
    @patch("src.etl.executor.ClinicalConductorClient")
    @patch("src.etl.executor.DataLoader")
    def test_execute_job_non_parameterized(
        self, mock_data_loader_class, mock_api_client_class, mock_pool
    ):
        """Test executing non-parameterized job."""
        # Mock database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor

        # Mock job config query
        mock_cursor.fetchone.side_effect = [
            {
                "id": 1,
                "name": "Test Job",
                "source_endpoint": "/api/v1/studies/odata",
                "target_table": "dim_studies_staging",
                "is_active": True,
                "requires_parameters": False,
                "parameter_source_table": None,
                "parameter_source_column": None,
                "source_instance_id": None,
                "description": None,
            },
            (datetime.now(),),  # started_at for update_run
        ]

        # Mock API client
        mock_api_client = MagicMock()
        mock_page = MagicMock()
        mock_page.items = [{"id": "1", "name": "Test"}]
        mock_api_client.get_odata.return_value = iter([mock_page])
        mock_api_client_class.return_value = mock_api_client

        # Mock data loader
        mock_data_loader = MagicMock()
        mock_load_result = MagicMock()
        mock_load_result.rows_inserted = 1
        mock_load_result.rows_updated = 0
        mock_data_loader.load_to_staging.return_value = mock_load_result
        mock_data_loader_class.return_value = mock_data_loader

        executor = JobExecutor(
            api_client=mock_api_client, data_loader=mock_data_loader
        )

        result = executor.execute_job(job_id=1, dry_run=False)

        assert result.status == "success"
        assert result.records_loaded == 1
        assert result.run_id is not None

    @patch("src.etl.executor.get_pool")
    @patch("src.etl.executor.ClinicalConductorClient")
    @patch("src.etl.executor.DataLoader")
    def test_execute_job_dry_run(
        self, mock_data_loader_class, mock_api_client_class, mock_pool
    ):
        """Test executing job in dry-run mode."""
        # Mock database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor

        # Mock job config query
        mock_cursor.fetchone.side_effect = [
            {
                "id": 1,
                "name": "Test Job",
                "source_endpoint": "/api/v1/studies/odata",
                "target_table": "dim_studies_staging",
                "is_active": True,
                "requires_parameters": False,
                "parameter_source_table": None,
                "parameter_source_column": None,
                "source_instance_id": None,
                "description": None,
            },
            (datetime.now(),),  # started_at for update_run
        ]

        # Mock API client
        mock_api_client = MagicMock()
        mock_page = MagicMock()
        mock_page.items = [{"id": "1"}]
        mock_api_client.get_odata.return_value = iter([mock_page])
        mock_api_client_class.return_value = mock_api_client

        # Mock data loader
        mock_data_loader = MagicMock()
        mock_data_loader_class.return_value = mock_data_loader

        executor = JobExecutor(
            api_client=mock_api_client, data_loader=mock_data_loader
        )

        result = executor.execute_job(job_id=1, dry_run=True)

        # In dry-run, data loader should not be called
        mock_data_loader.load_to_staging.assert_not_called()
        assert result.status == "success"
        assert result.records_loaded == 1  # Counts items fetched, not loaded

    def teardown_method(self):
        """Clean up test environment."""
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("CC_API_BASE_URL", None)
        os.environ.pop("CC_API_KEY", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DRY_RUN", None)

