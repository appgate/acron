import asyncio
from datetime import datetime

import pytest

from acron.scheduler import Scheduler
from acron.job import job_context, SimpleJob


@pytest.mark.asyncio
async def test_start_stop():
    s = Scheduler()
    assert s.running is False
    s.start()
    assert s.running is True
    s.stop()
    await s.wait()
    assert s.running is False


@pytest.mark.asyncio
async def test_context_manager():
    async with Scheduler() as s:
        assert s.running is True
    assert s.running is False


@pytest.mark.asyncio
async def test_schedule_job():
    s = Scheduler()
    job_ran = asyncio.Event()

    async def job_func():
        # Make sure the context var is working
        assert job_context().scheduled_job.job.name == "test"
        job_ran.set()

    test_job = SimpleJob(
        name="test", schedule="0/1 * * * *", enabled=True, func=job_func
    )
    jobs = {test_job}
    now = datetime.now()
    s.process_jobs_update(jobs, now=now)
    s.schedule_jobs()
    scheduled_jobs = s.scheduled_jobs()

    # Make sure the same job is scheduled 32 times
    assert len(scheduled_jobs) == 32

    # Make sure jobs are scheduled every minute
    first_time = scheduled_jobs[0].when
    assert [sj.when - first_time for sj in scheduled_jobs] == [
        i * 60.0 for i in range(len(scheduled_jobs))
    ]

    # Make sure the correct job is scheduled
    for sj in scheduled_jobs:
        assert sj.job == test_job
        await sj.run()
        assert job_ran.is_set()
        job_ran.clear()
