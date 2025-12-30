import pytest
from src.etl.orchestrator import ETLOrchestrator, ETLJob


class FakeDB:
    def __init__(self, job_row):
        self.job_row = job_row
        self.created_runs = []
        self.updated_runs = []

    def get_job_config(self, job_id):
        return self.job_row

    def create_run(self, job_id):
        run_id = 123
        self.created_runs.append((job_id, run_id))
        return run_id

    def update_run(self, run_id, **kwargs):
        self.updated_runs.append((run_id, kwargs))


class FakeAPI:
    def __init__(self, records):
        self.records = records

    def get_odata(self, endpoint):
        return self.records


class FakeLoader:
    def __init__(self):
        self.loaded = []

    def load_to_staging(self, table_name, records, job_id, run_id):
        self.loaded.append((table_name, len(records), job_id, run_id))


def test_execute_job_success():
    job_row = {
        'id': 1,
        'name': 'test',
        'source_endpoint': '/odata/tests',
        'target_table': 'dim_test_staging',
        'is_active': True,
        'requires_parameters': False,
        'parameter_source_table': None,
        'parameter_source_column': None,
    }
    db = FakeDB(job_row)
    api = FakeAPI([{'id': 1}, {'id': 2}])
    loader = FakeLoader()
    orch = ETLOrchestrator(db, api, loader)

    result = orch.execute_job(1)

    assert result.status == 'success'
    assert result.records_loaded == 2
    assert db.created_runs[0][0] == 1
    assert loader.loaded[0][0] == 'dim_test_staging'
    # ensure run updated with success
    statuses = [u[1]['status'] for u in db.updated_runs]
    assert 'success' in statuses


def test_execute_job_failure_raises_and_logs():
    job_row = {
        'id': 2,
        'name': 'bad',
        'source_endpoint': '/odata/bad',
        'target_table': 'dim_bad_staging',
        'is_active': True,
        'requires_parameters': False,
        'parameter_source_table': None,
        'parameter_source_column': None,
    }
    class BoomAPI:
        def get_odata(self, endpoint):
            raise RuntimeError('boom')

    class DummyLogger:
        def __init__(self):
            self.errors = []
        def error(self, *args, **kwargs):
            self.errors.append((args, kwargs))

    db = FakeDB(job_row)
    api = BoomAPI()
    loader = FakeLoader()
    log = DummyLogger()
    orch = ETLOrchestrator(db, api, loader, logger=log)

    with pytest.raises(RuntimeError):
        orch.execute_job(2)

    statuses = [u[1]['status'] for u in db.updated_runs]
    assert 'failed' in statuses
    assert any('error' in k for _, k in log.errors)
