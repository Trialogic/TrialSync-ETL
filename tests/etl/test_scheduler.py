from apscheduler.triggers.cron import CronTrigger
from src.etl.scheduler import JobScheduler

class DummyOrchestrator:
    def __init__(self):
        self.executed = []
    def execute_job(self, job_id: int):
        self.executed.append(job_id)


def test_schedule_job_parses_cron_and_adds_job():
    orch = DummyOrchestrator()
    sched = JobScheduler(orch)
    trigger = CronTrigger.from_crontab("0 3 * * *")
    assert trigger.fields[0].__class__.__name__.lower().startswith("minute")
    # ensure no exceptions on schedule
    sched.schedule_job(42, "0 3 * * *")
    job = sched._scheduler.get_job("etl-job-42")
    assert job is not None
    sched.shutdown()


def test_refresh_from_rows_idempotent():
    orch = DummyOrchestrator()
    sched = JobScheduler(orch)
    rows = [
        {"job_id": 1, "cron_expression": "0 2 * * *", "enabled": True},
        {"job_id": 2, "cron_expression": "0 3 * * *", "enabled": False},
    ]
    added = sched.refresh_from_rows(rows)
    assert added == 1
    assert sched._scheduler.get_job("etl-job-1") is not None
    assert sched._scheduler.get_job("etl-job-2") is None
    sched.shutdown()
