"""ETL Orchestrator.

Manages dependency-aware execution of ETL jobs with parallel execution,
scheduling, and retry logic.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Optional

import structlog
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config import get_settings
from src.etl.executor import ExecutionResult, JobExecutor
from src.metrics import get_metrics_collector

logger = structlog.get_logger(__name__)


@dataclass
class JobNode:
    """Node in the job dependency graph."""

    job_id: int
    name: str
    dependencies: list[int]  # List of job IDs this job depends on
    dependents: list[int]  # List of job IDs that depend on this job


class DependencyGraph:
    """Dependency graph for ETL jobs."""

    def __init__(self):
        """Initialize dependency graph."""
        self.nodes: dict[int, JobNode] = {}
        self.edges: list[tuple[int, int]] = []  # (parent, child) edges

    def add_job(self, job_id: int, name: str, dependencies: Optional[list[int]] = None):
        """Add a job to the graph.

        Args:
            job_id: Job ID.
            name: Job name.
            dependencies: List of job IDs this job depends on.
        """
        if job_id not in self.nodes:
            self.nodes[job_id] = JobNode(
                job_id=job_id,
                name=name,
                dependencies=dependencies or [],
                dependents=[],
            )

            # Add edges
            for dep_id in dependencies or []:
                self.edges.append((dep_id, job_id))

        # Update dependents
        for dep_id in dependencies or []:
            if dep_id in self.nodes:
                if job_id not in self.nodes[dep_id].dependents:
                    self.nodes[dep_id].dependents.append(job_id)

    def validate_dag(self) -> tuple[bool, Optional[list[int]]]:
        """Validate that the graph is acyclic (DAG).

        Returns:
            Tuple of (is_valid, cycle_if_any).
        """
        # Kahn's algorithm for cycle detection
        in_degree = defaultdict(int)
        for node in self.nodes.values():
            in_degree[node.job_id] = len(node.dependencies)

        queue = deque([node.job_id for node in self.nodes.values() if in_degree[node.job_id] == 0])
        processed = 0

        while queue:
            node_id = queue.popleft()
            processed += 1

            for dependent_id in self.nodes[node_id].dependents:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        if processed != len(self.nodes):
            # Cycle detected - find it
            cycle = self._find_cycle()
            return (False, cycle)

        return (True, None)

    def _find_cycle(self) -> list[int]:
        """Find a cycle in the graph (simplified).

        Returns:
            List of job IDs forming a cycle.
        """
        # Simple DFS-based cycle detection
        visited = set()
        rec_stack = set()
        cycle_path = []

        def dfs(node_id: int) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            cycle_path.append(node_id)

            for dep_id in self.nodes[node_id].dependencies:
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    # Cycle found
                    cycle_path.append(dep_id)
                    return True

            rec_stack.remove(node_id)
            cycle_path.pop()
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return cycle_path

        return []

    def topological_sort(self) -> list[list[int]]:
        """Topological sort of jobs for execution order.

        Returns:
            List of job ID lists, where each inner list can be executed in parallel.
        """
        in_degree = defaultdict(int)
        for node in self.nodes.values():
            in_degree[node.job_id] = len(node.dependencies)

        result = []
        queue = deque([node.job_id for node in self.nodes.values() if in_degree[node.job_id] == 0])

        while queue:
            # Current level (can be executed in parallel)
            current_level = []
            level_size = len(queue)

            for _ in range(level_size):
                node_id = queue.popleft()
                current_level.append(node_id)

                # Update dependents
                for dependent_id in self.nodes[node_id].dependents:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

            if current_level:
                result.append(current_level)

        return result


class ETLOrchestrator:
    """Orchestrates ETL job execution.

    Manages dependency-aware execution, parallel processing, and scheduling.
    """

    def __init__(
        self,
        job_executor: Optional[JobExecutor] = None,
        max_parallel_jobs: Optional[int] = None,
    ):
        """Initialize orchestrator.

        Args:
            job_executor: JobExecutor instance. If None, creates one.
            max_parallel_jobs: Maximum parallel jobs. If None, uses settings.
        """
        self.job_executor = job_executor or JobExecutor()
        settings = get_settings()
        self.max_parallel_jobs = max_parallel_jobs or settings.etl.max_parallel_jobs
        self.pool = self.job_executor.pool

    def build_dependency_graph(self, job_ids: Optional[list[int]] = None) -> DependencyGraph:
        """Build dependency graph from database.

        Args:
            job_ids: Specific job IDs to include. If None, includes all active jobs.

        Returns:
            DependencyGraph instance.

        Raises:
            ValueError: If graph contains cycles or invalid dependencies.
        """
        graph = DependencyGraph()
        
        with self.pool.get_connection() as conn:
            import psycopg2.extras
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if job_ids:
                placeholders = ','.join(['%s'] * len(job_ids))
                query = f"""
                    SELECT id, name, COALESCE(depends_on, ARRAY[]::INTEGER[]) as depends_on
                    FROM dw_etl_jobs
                    WHERE id IN ({placeholders}) AND is_active = TRUE
                """
                cursor.execute(query, job_ids)
            else:
                cursor.execute(
                    """
                    SELECT id, name, COALESCE(depends_on, ARRAY[]::INTEGER[]) as depends_on
                    FROM dw_etl_jobs
                    WHERE is_active = TRUE
                    """
                )
            
            jobs = cursor.fetchall()
            
            # Add all jobs to graph first
            for job in jobs:
                job_id = job['id']
                name = job['name']
                depends_on = job['depends_on'] or []
                
                # Validate that all dependencies exist
                if depends_on:
                    dep_ids_str = ','.join([str(d) for d in depends_on])
                    cursor.execute(
                        f"""
                        SELECT id FROM dw_etl_jobs
                        WHERE id IN ({dep_ids_str})
                        """
                    )
                    existing_deps = {row['id'] for row in cursor.fetchall()}
                    missing_deps = set(depends_on) - existing_deps
                    if missing_deps:
                        raise ValueError(
                            f"Job {job_id} ({name}) depends on missing jobs: {missing_deps}"
                        )
                
                graph.add_job(job_id, name, depends_on)

        # Validate DAG
        is_valid, cycle = graph.validate_dag()
        if not is_valid:
            raise ValueError(f"Dependency graph contains cycle: {cycle}")

        return graph

    def execute_jobs(
        self,
        job_ids: Optional[list[int]] = None,
        dry_run: bool = False,
        max_parallel: Optional[int] = None,
    ) -> dict[int, ExecutionResult]:
        """Execute jobs with dependency-aware ordering.

        Args:
            job_ids: Specific job IDs to execute. If None, executes all active jobs.
            dry_run: If True, don't write to database.
            max_parallel: Maximum parallel jobs. If None, uses instance default.

        Returns:
            Dictionary mapping job_id to ExecutionResult.
        """
        max_parallel = max_parallel or self.max_parallel_jobs

        # Build dependency graph
        graph = self.build_dependency_graph(job_ids)

        # Topological sort
        execution_order = graph.topological_sort()

        logger.info(
            "orchestrator_execution_started",
            total_jobs=len(graph.nodes),
            execution_levels=len(execution_order),
            max_parallel=max_parallel,
            dry_run=dry_run,
        )

        # Initialize metrics
        metrics_collector = get_metrics_collector()
        metrics_collector.update_running_jobs(0)

        results: dict[int, ExecutionResult] = {}
        failed_jobs: set[int] = set()

        # Execute in topological order
        for level in execution_order:
            # Filter out failed jobs' dependents
            level_jobs = [job_id for job_id in level if job_id not in failed_jobs]

            if not level_jobs:
                continue

            # Update running jobs metric
            metrics_collector.update_running_jobs(len(level_jobs))

            # Execute level jobs in parallel (bounded)
            level_results = self._execute_level(
                job_ids=level_jobs,
                dry_run=dry_run,
                max_parallel=max_parallel,
            )

            results.update(level_results)

            # Track failed jobs
            for job_id, result in level_results.items():
                if result.status == "failed":
                    failed_jobs.add(job_id)

            # Update running jobs metric (jobs completed)
            metrics_collector.update_running_jobs(0)

            # Mark dependents of failed jobs as skipped
            for job_id in failed_jobs:
                node = graph.nodes.get(job_id)
                if node:
                    for dependent_id in node.dependents:
                        if dependent_id not in results:
                            # Create skipped result
                            results[dependent_id] = ExecutionResult(
                                run_id=0,  # No run created
                                status="skipped",
                                error_message=f"Upstream job {job_id} failed",
                            )

        # Reset running jobs metric
        metrics_collector.update_running_jobs(0)

        logger.info(
            "orchestrator_execution_completed",
            total_jobs=len(results),
            successful=sum(1 for r in results.values() if r.status == "success"),
            failed=sum(1 for r in results.values() if r.status == "failed"),
            skipped=sum(1 for r in results.values() if r.status == "skipped"),
        )

        return results

    def _execute_level(
        self,
        job_ids: list[int],
        dry_run: bool,
        max_parallel: int,
    ) -> dict[int, ExecutionResult]:
        """Execute a level of jobs in parallel.

        Args:
            job_ids: Job IDs to execute.
            dry_run: If True, don't write to database.
            max_parallel: Maximum parallel jobs.

        Returns:
            Dictionary mapping job_id to ExecutionResult.
        """
        results: dict[int, ExecutionResult] = {}

        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(self.job_executor.execute_job, job_id, dry_run): job_id
                for job_id in job_ids
            }

            # Collect results as they complete
            for future in as_completed(future_to_job):
                job_id = future_to_job[future]
                try:
                    result = future.result()
                    results[job_id] = result

                    logger.info(
                        "job_execution_completed",
                        job_id=job_id,
                        status=result.status,
                        records_loaded=result.records_loaded,
                        duration_seconds=result.duration_seconds,
                    )
                except Exception as e:
                    logger.error(
                        "job_execution_exception",
                        job_id=job_id,
                        error=str(e),
                    )
                    results[job_id] = ExecutionResult(
                        run_id=0,
                        status="failed",
                        error_message=str(e),
                    )

        return results

    def execute_all_active_jobs(self, dry_run: bool = False) -> dict[int, ExecutionResult]:
        """Execute all active jobs.

        Args:
            dry_run: If True, don't write to database.

        Returns:
            Dictionary mapping job_id to ExecutionResult.
        """
        return self.execute_jobs(job_ids=None, dry_run=dry_run)

    def get_job_status(self, job_id: int) -> Optional[dict[str, Any]]:
        """Get current status of a job.

        Args:
            job_id: Job ID.

        Returns:
            Dictionary with job status information, or None if not found.
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, is_active, last_run_at, last_run_status, last_run_records
                FROM dw_etl_jobs
                WHERE id = %s
                """,
                (job_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "job_id": row[0],
                "name": row[1],
                "is_active": row[2],
                "last_run_at": row[3],
                "last_run_status": row[4],
                "last_run_records": row[5],
            }

