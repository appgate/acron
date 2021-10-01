import asyncio
import dataclasses

import pytest

from acron import __version__
from acron.scheduler import Scheduler, Job


def test_version():
    assert __version__ == '0.1.0'


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
async def test_run_job():
    async with Scheduler() as s:
        job_ran = asyncio.Event()
        await s.update_jobs({
            Job(
                name='test',
                schedule='0/1 * * * *',
                enabled=True,
                func=lambda: job_ran.set()
            )
        })
        await asyncio.wait_for(job_ran.wait(), 70.0)
