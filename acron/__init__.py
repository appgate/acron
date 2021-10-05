from datetime import timezone
from typing import Iterable, Optional

from acron.job import Job


__all__ = [
    "__version__",
    "run",
    "Job",
]


__version__ = "0.1.8"


async def run(jobs: Iterable[Job], tz: Optional[timezone] = None) -> None:
    """
    Run given jobs with given timezone forever.
    """
    from acron.scheduler import Scheduler

    async with Scheduler(tz=tz) as _scheduler:
        await _scheduler.update_jobs(set(jobs))
        await _scheduler.wait()
