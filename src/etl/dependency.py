from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

@dataclass(frozen=True)
class JobRef:
    id: int
    name: str | None = None
    is_active: bool = True

class DependencyError(Exception):
    pass

class CycleDetectedError(DependencyError):
    def __init__(self, cycle_nodes: List[int]):
        msg = f"Cycle detected in job dependencies: {cycle_nodes}"
        super().__init__(msg)
        self.cycle_nodes = cycle_nodes

class UnknownJobError(DependencyError):
    def __init__(self, job_id: int):
        super().__init__(f"Dependency references unknown job_id={job_id}")
        self.job_id = job_id


def _build_graph(job_ids: Set[int], deps: Iterable[Tuple[int, int]]):
    adj: Dict[int, Set[int]] = {j: set() for j in job_ids}
    indeg: Dict[int, int] = {j: 0 for j in job_ids}

    for parent, child in deps:
        if parent not in job_ids:
            raise UnknownJobError(parent)
        if child not in job_ids:
            raise UnknownJobError(child)
        if child not in adj[parent]:
            adj[parent].add(child)
            indeg[child] += 1
    return adj, indeg


def topological_batches(
    jobs: Iterable[JobRef],
    dependencies: Iterable[Tuple[int, int]],
) -> List[List[int]]:
    """
    Return a list of batches, where each batch is a list of job_ids that can run in parallel.

    - Filters to active jobs only
    - Validates unknown job references
    - Detects cycles and raises CycleDetectedError
    """
    active_ids: Set[int] = {j.id for j in jobs if j.is_active}
    adj, indeg = _build_graph(active_ids, dependencies)

    # Kahn's algorithm producing level-by-level batches
    batches: List[List[int]] = []
    ready: List[int] = sorted([j for j, d in indeg.items() if d == 0])
    processed = 0

    while ready:
        batch = ready
        batches.append(batch)
        ready = []
        for u in batch:
            processed += 1
            for v in sorted(adj[u]):
                indeg[v] -= 1
                if indeg[v] == 0:
                    ready.append(v)
        ready.sort()

    if processed != len(active_ids):
        # find remaining nodes to help debugging cycles
        remaining = [j for j, d in indeg.items() if d > 0]
        raise CycleDetectedError(remaining)

    return batches


def linear_order(
    jobs: Iterable[JobRef],
    dependencies: Iterable[Tuple[int, int]],
) -> List[int]:
    """Flatten batches into a single topological order (stable by job id)."""
    order: List[int] = []
    for batch in topological_batches(jobs, dependencies):
        order.extend(batch)
    return order
