import logging
from datetime import timezone
from typing import Iterable, Optional

from acron.job import Job, SimpleJob


__all__ = ["__version__", "run", "Job", "SimpleJob", "logger"]


__version__ = "0.2.1"


logger = logging.getLogger("acron")


async def run(jobs: Iterable[Job], tz: Optional[timezone] = None) -> None:
    """
    Run given jobs with given timezone forever.
    """
    from acron.scheduler import Scheduler

    async with Scheduler(tz=tz) as _scheduler:
        await _scheduler.update_jobs(set(jobs))
        await _scheduler.wait()
