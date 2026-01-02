"""Settings loader for TrialSync ETL.

Loads configuration from environment variables and YAML files.
Uses Pydantic for validation and type safety.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        extra="ignore",
    )

    url: str = Field(
        ...,
        description="PostgreSQL connection URL (postgresql://user:pass@host:port/dbname)",
    )
    pool_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Connection pool size",
    )
    max_overflow: int = Field(
        default=10,
        ge=0,
        description="Maximum overflow connections",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("DATABASE_URL must start with postgresql://")
        return v


class APISettings(BaseSettings):
    """Clinical Conductor API settings."""

    model_config = SettingsConfigDict(
        env_prefix="CC_API_",
        extra="ignore",
    )

    base_url: str = Field(
        ...,
        description="Base URL for Clinical Conductor API (without trailing slash)",
    )
    key: str = Field(
        ...,
        description="API key for authentication (X-ApiKey header)",
    )
    timeout: int = Field(
        default=30000,
        ge=1000,
        description="Request timeout in milliseconds",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retries for failed requests",
    )
    retry_delay_seconds: float = Field(
        default=1.0,
        ge=0.1,
        description="Initial retry delay in seconds",
    )
    rate_limit_per_second: float = Field(
        default=10.0,
        ge=0.1,
        description="Rate limit (requests per second)",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate and normalize base URL."""
        v = v.rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("CC_API_BASE_URL must start with http:// or https://")
        return v


class ETLSettings(BaseSettings):
    """ETL execution settings."""

    model_config = SettingsConfigDict(
        env_prefix="ETL_",
        extra="ignore",
    )

    batch_size: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Batch size for bulk inserts",
    )
    max_parallel_jobs: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of parallel jobs",
    )
    default_timeout_seconds: int = Field(
        default=300,
        ge=10,
        description="Default job timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retries for failed jobs",
    )
    retry_delay_seconds: int = Field(
        default=5,
        ge=1,
        description="Initial retry delay in seconds",
    )
    retry_backoff_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        description="Retry backoff multiplier",
    )


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        extra="ignore",
    )

    level: str = Field(
        default="INFO",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    format: str = Field(
        default="json",
        description="Log format (json, console)",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()


class Settings(BaseSettings):
    """Main application settings.

    Combines all configuration sources:
    - Environment variables (highest priority)
    - YAML config file (config/jobs.yaml)
    - Default values (lowest priority)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = Field(
        default="development",
        description="Environment (development, test, production)",
    )
    dry_run: bool = Field(
        default=True,
        description="Dry run mode (no network/DB writes in dev/test)",
    )

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    etl: ETLSettings = Field(default_factory=ETLSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # Job configuration file path
    jobs_config_path: Path = Field(
        default=Path("config/jobs.yaml"),
        description="Path to YAML job configuration file",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = {"development", "test", "production"}
        if v.lower() not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}")
        return v.lower()

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment == "test"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    def load_jobs_config(self) -> Optional[dict]:
        """Load job configuration from YAML file.

        Returns:
            Dictionary with job configuration, or None if file doesn't exist.

        Raises:
            ValueError: If YAML file exists but is invalid.
        """
        if not self.jobs_config_path.exists():
            return None

        try:
            with open(self.jobs_config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {self.jobs_config_path}: {e}") from e

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings instance from environment variables.

        This is the recommended way to create settings.
        """
        # Load .env file if it exists
        env_file = Path(".env")
        if env_file.exists():
            from dotenv import load_dotenv

            load_dotenv(env_file)

        return cls()


# Global settings instance (lazy-loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance.

    Returns:
        Settings instance (singleton pattern).
    """
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment.

    Useful for testing or when environment variables change.

    Returns:
        New Settings instance.
    """
    global _settings
    _settings = Settings.from_env()
    return _settings

