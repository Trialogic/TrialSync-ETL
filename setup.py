"""Setup script for TrialSync ETL."""

from setuptools import find_packages, setup

setup(
    name="trialsync-etl",
    version="1.0.0",
    description="ETL system for synchronizing clinical trial data from Clinical Conductor API",
    packages=find_packages(),
    python_requires=">=3.12",
    install_requires=[
        "click>=8.1.7",
        "rich>=13.7.0",
        "psycopg2-binary>=2.9.9",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "APScheduler>=3.10.4",
        "structlog>=24.1.0",
        "pyyaml>=6.0.1",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "tenacity>=8.2.3",
        "prometheus-client>=0.19.0",
    ],
    entry_points={
        "console_scripts": [
            "trialsync-etl=src.cli.main:main",
        ],
    },
)

