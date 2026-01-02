"""Tests for ETL orchestrator module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.etl import DependencyGraph, ETLOrchestrator, ExecutionResult
from src.config import reload_settings


class TestDependencyGraph:
    """Tests for DependencyGraph."""

    def test_add_job(self):
        """Test adding jobs to graph."""
        graph = DependencyGraph()
        graph.add_job(1, "Job 1")
        graph.add_job(2, "Job 2", dependencies=[1])

        assert 1 in graph.nodes
        assert 2 in graph.nodes
        assert 2 in graph.nodes[1].dependents
        assert 1 in graph.nodes[2].dependencies

    def test_validate_dag_valid(self):
        """Test validating a valid DAG."""
        graph = DependencyGraph()
        graph.add_job(1, "Job 1")
        graph.add_job(2, "Job 2", dependencies=[1])
        graph.add_job(3, "Job 3", dependencies=[1, 2])

        is_valid, cycle = graph.validate_dag()
        assert is_valid is True
        assert cycle is None

    def test_validate_dag_cycle(self):
        """Test detecting cycles in graph."""
        graph = DependencyGraph()
        graph.add_job(1, "Job 1", dependencies=[2])
        graph.add_job(2, "Job 2", dependencies=[1])

        is_valid, cycle = graph.validate_dag()
        assert is_valid is False
        assert cycle is not None

    def test_topological_sort(self):
        """Test topological sorting."""
        graph = DependencyGraph()
        graph.add_job(1, "Job 1")
        graph.add_job(2, "Job 2", dependencies=[1])
        graph.add_job(3, "Job 3", dependencies=[1])
        graph.add_job(4, "Job 4", dependencies=[2, 3])

        order = graph.topological_sort()

        # Should have multiple levels
        assert len(order) > 1
        # Level 0 should have job 1
        assert 1 in order[0]
        # Level 1 should have jobs 2 and 3 (can run in parallel)
        assert 2 in order[1] or 3 in order[1]
        # Level 2 should have job 4
        assert 4 in order[-1]


class TestETLOrchestrator:
    """Tests for ETLOrchestrator."""

    def setup_method(self):
        """Set up test environment."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/test_db"
        os.environ["CC_API_BASE_URL"] = "https://test-api.example.com"
        os.environ["CC_API_KEY"] = "test-key"
        os.environ["ENVIRONMENT"] = "test"
        os.environ["DRY_RUN"] = "false"
        reload_settings()

    @patch("src.etl.orchestrator.get_pool")
    def test_build_dependency_graph(self, mock_pool):
        """Test building dependency graph from database."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            (1, "Job 1", True),
            (2, "Job 2", True),
        ]

        orchestrator = ETLOrchestrator()
        graph = orchestrator.build_dependency_graph()

        assert len(graph.nodes) == 2
        assert 1 in graph.nodes
        assert 2 in graph.nodes

    @patch("src.etl.orchestrator.JobExecutor")
    @patch("src.etl.orchestrator.get_pool")
    def test_execute_jobs(self, mock_pool, mock_executor_class):
        """Test executing jobs with orchestrator."""
        # Mock database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            (1, "Job 1", True),
            (2, "Job 2", True),
        ]

        # Mock executor
        mock_executor = MagicMock()
        mock_result = ExecutionResult(
            run_id=123,
            status="success",
            records_loaded=10,
        )
        mock_executor.execute_job.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        orchestrator = ETLOrchestrator(job_executor=mock_executor)
        results = orchestrator.execute_jobs(job_ids=[1, 2])

        assert len(results) == 2
        assert results[1].status == "success"
        assert results[2].status == "success"

    @patch("src.etl.orchestrator.get_pool")
    def test_get_job_status(self, mock_pool):
        """Test getting job status."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (
            1,
            "Test Job",
            True,
            None,  # last_run_at
            None,  # last_run_status
            None,  # last_run_records
        )

        orchestrator = ETLOrchestrator()
        status = orchestrator.get_job_status(1)

        assert status is not None
        assert status["job_id"] == 1
        assert status["name"] == "Test Job"

    @patch("src.etl.orchestrator.get_pool")
    def test_get_job_status_not_found(self, mock_pool):
        """Test getting status for non-existent job."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        orchestrator = ETLOrchestrator()
        status = orchestrator.get_job_status(999)

        assert status is None

    def teardown_method(self):
        """Clean up test environment."""
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("CC_API_BASE_URL", None)
        os.environ.pop("CC_API_KEY", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DRY_RUN", None)

