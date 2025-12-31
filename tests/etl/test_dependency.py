from src.etl.dependency import JobRef, topological_batches, linear_order, CycleDetectedError, UnknownJobError


def test_parallel_batches_and_order():
    jobs = [JobRef(1), JobRef(2), JobRef(3), JobRef(4)]
    deps = [(1, 3), (2, 3), (3, 4)]
    batches = topological_batches(jobs, deps)
    # 1 and 2 parallel, then 3, then 4
    assert batches == [[1, 2], [3], [4]]
    assert linear_order(jobs, deps) == [1, 2, 3, 4]


def test_cycle_detection():
    jobs = [JobRef(1), JobRef(2), JobRef(3)]
    deps = [(1, 2), (2, 3), (3, 1)]
    try:
        topological_batches(jobs, deps)
        assert False, "Expected CycleDetectedError"
    except CycleDetectedError as e:
        assert set(e.cycle_nodes) == {1, 2, 3}


def test_unknown_job_reference():
    jobs = [JobRef(1), JobRef(2)]
    deps = [(1, 99)]
    try:
        topological_batches(jobs, deps)
        assert False, "Expected UnknownJobError"
    except UnknownJobError as e:
        assert e.job_id == 99
