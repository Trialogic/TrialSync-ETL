"""Tests for configuration module."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config import (
    PreflightError,
    Settings,
    check_api_host,
    check_database_write,
    check_environment,
    check_network_request,
    get_dry_run_status,
    get_settings,
    preflight_check,
    reload_settings,
)


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        # Set required environment variables
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        os.environ["CC_API_KEY"] = "test-key"
        os.environ["ENVIRONMENT"] = "development"
        os.environ["DRY_RUN"] = "true"

        settings = reload_settings()

        assert settings.environment == "development"
        assert settings.dry_run is True
        assert settings.etl.batch_size == 1000
        assert settings.etl.max_parallel_jobs == 5
        assert settings.api.timeout == 30000

    def test_environment_validation(self):
        """Test environment validation."""
        os.environ["ENVIRONMENT"] = "invalid"
        with pytest.raises(ValueError, match="ENVIRONMENT must be one of"):
            reload_settings()

        os.environ["ENVIRONMENT"] = "production"
        settings = reload_settings()
        assert settings.environment == "production"
        assert settings.is_production is True

    def test_load_jobs_config(self):
        """Test loading jobs config from YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {
                "jobs": {
                    "test_job": {
                        "enabled": True,
                        "schedule": "0 1 * * *",
                    }
                },
                "settings": {
                    "max_parallel_jobs": 10,
                },
            }
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            os.environ["JOBS_CONFIG_PATH"] = str(config_path)
            settings = reload_settings()
            jobs_config = settings.load_jobs_config()

            assert jobs_config is not None
            assert "jobs" in jobs_config
            assert "test_job" in jobs_config["jobs"]
        finally:
            config_path.unlink()
            os.environ.pop("JOBS_CONFIG_PATH", None)

    def test_load_jobs_config_missing_file(self):
        """Test loading jobs config when file doesn't exist."""
        os.environ["JOBS_CONFIG_PATH"] = "/nonexistent/path/jobs.yaml"
        settings = reload_settings()
        jobs_config = settings.load_jobs_config()
        assert jobs_config is None

    def test_database_url_validation(self):
        """Test database URL validation."""
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        os.environ["CC_API_KEY"] = "test-key"
        os.environ["DATABASE_URL"] = "invalid://url"
        with pytest.raises(ValueError, match="DATABASE_URL must start with postgresql://"):
            reload_settings()

        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        settings = reload_settings()
        assert settings.database.url.startswith("postgresql://")

    def test_api_base_url_validation(self):
        """Test API base URL validation."""
        os.environ["CC_API_BASE_URL"] = "invalid-url"
        with pytest.raises(ValueError, match="CC_API_BASE_URL must start with"):
            reload_settings()

        os.environ["CC_API_BASE_URL"] = "https://api.example.com"
        settings = reload_settings()
        assert settings.api.base_url == "https://api.example.com"

    def test_api_base_url_normalization(self):
        """Test API base URL trailing slash removal."""
        os.environ["CC_API_BASE_URL"] = "https://api.example.com/"
        settings = reload_settings()
        assert settings.api.base_url == "https://api.example.com"


class TestPreflightChecks:
    """Tests for preflight safety checks."""

    def setup_method(self):
        """Set up test environment."""
        # Reset to safe defaults
        os.environ["ENVIRONMENT"] = "development"
        os.environ["DRY_RUN"] = "true"
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        os.environ["CC_API_KEY"] = "test-key"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        reload_settings()

    def test_check_environment_dev_with_dry_run(self):
        """Test environment check in dev with DRY_RUN=true (should pass)."""
        check_environment()  # Should not raise

    def test_check_environment_dev_without_dry_run(self):
        """Test environment check in dev without DRY_RUN (should fail)."""
        os.environ["DRY_RUN"] = "false"
        reload_settings()

        with pytest.raises(PreflightError, match="DRY_RUN must be true"):
            check_environment()

    def test_check_api_host_production_in_dev(self):
        """Test API host check blocks production API in dev."""
        os.environ["CC_API_BASE_URL"] = "https://tektonresearch.clinicalconductor.com/CCSWEB"
        reload_settings()

        with pytest.raises(PreflightError, match="Cannot call production API"):
            check_api_host()

    def test_check_api_host_test_in_dev(self):
        """Test API host check allows test API in dev."""
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        reload_settings()

        check_api_host()  # Should not raise

    def test_check_database_write_in_dry_run(self):
        """Test database write check blocks writes in DRY_RUN."""
        with pytest.raises(PreflightError, match="Database writes are disabled"):
            check_database_write()

    def test_check_database_write_without_dry_run(self):
        """Test database write check allows writes without DRY_RUN."""
        os.environ["DRY_RUN"] = "false"
        os.environ["ENVIRONMENT"] = "production"
        reload_settings()

        check_database_write()  # Should not raise

    def test_check_network_request_in_dry_run(self):
        """Test network request check blocks requests in DRY_RUN."""
        with pytest.raises(PreflightError, match="Network requests are disabled"):
            check_network_request()

    def test_preflight_check_combined(self):
        """Test combined preflight check."""
        # Should fail on network check
        with pytest.raises(PreflightError, match="Network requests are disabled"):
            preflight_check(allow_network=True)

        # Should fail on DB write check
        with pytest.raises(PreflightError, match="Database writes are disabled"):
            preflight_check(allow_db_write=True)

    def test_get_dry_run_status(self):
        """Test getting dry run status."""
        is_dry_run, reason = get_dry_run_status()
        assert is_dry_run is True
        assert "DRY_RUN=true" in reason

        os.environ["DRY_RUN"] = "false"
        os.environ["ENVIRONMENT"] = "production"
        reload_settings()

        is_dry_run, reason = get_dry_run_status()
        assert is_dry_run is False
        assert reason is None

    def teardown_method(self):
        """Clean up test environment."""
        # Restore safe defaults
        os.environ["ENVIRONMENT"] = "development"
        os.environ["DRY_RUN"] = "true"
        reload_settings()

