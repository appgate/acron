import asyncio
import dataclasses
import functools
import itertools
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Set, Optional

from croniter import croniter
import pytz

__all__ = [
    "Job",
    "Scheduler",
]


log = logging.getLogger("acron")


def cron_date(timestamp: float, tz: timezone) -> str:
    fmt = "%Y-%m-%d %H:%M:%S %Z%z"
    return datetime.fromtimestamp(timestamp).astimezone(tz=tz).strftime(fmt)


@dataclasses.dataclass(frozen=True)
class Job:
    name: str
    schedule: str
    enabled: bool = True

    def __call__(self, dry_run: bool) -> None:
        # Default job that does nothing.
        pass


@dataclasses.dataclass(frozen=True)
class ScheduledJob:
    job: Job
    when: float
    event: asyncio.Event
    dry_run: bool
    id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))


ScheduledJobHandle = Tuple[ScheduledJob, asyncio.TimerHandle]


def croniter_sort_jobs(
    jobs: Set[Job], tz: timezone, n: int, offset: Optional[float]
) -> List[Tuple[float, Job]]:
    """
    Compute the n first tests needed to be scheduled from the test of tests.
    If offset is defined then the tests computed will be those that need to run after that time.
    """
    xs: List[Tuple[float, Job]] = []
    if offset:
        date = datetime.fromtimestamp(offset).astimezone(tz=tz)
    else:
        date = datetime.now(tz=tz)
    for job in jobs:
        xs.extend((d, job) for d in itertools.islice(croniter(job.schedule, date), n))

    new_jobs = sorted(xs, key=lambda i: i[0])
    last_job_time = new_jobs[n - 1][0]
    return list(itertools.takewhile(lambda i: i[0] <= last_job_time, new_jobs))


def cancel_old_jobs(
    generation: int, tasks: Dict[int, List[ScheduledJobHandle]]
) -> None:
    """
    Cancel all the scheduled tests.
    """
    for scheduled_test, hs in tasks.get(generation, []):
        scheduled_test.event.set()
        hs.cancel()


def remove_completed_jobs(gen: int, tasks: Dict[int, List[ScheduledJobHandle]]) -> None:
    """
    Removes the scheduled tests already completed.
    """
    xs = []
    for scheduled_test, hs in tasks.get(gen, []):
        if scheduled_test.event.is_set():
            continue
        xs.append((scheduled_test, hs))
    tasks[gen] = xs


def schedule_jobs(
    tasks: Dict[int, List[ScheduledJobHandle]],
    jobs: Set[Job],
    offset: Optional[float],
    n: int,
    generation: int,
    tz: timezone,
    dry_run: bool,
) -> float:
    """
    Schedule the next tests from the defined tests.
    It returns the timestamp for the last test scheduled.
    """
    loop = asyncio.get_running_loop()
    new_jobs = croniter_sort_jobs(jobs, tz, n, offset)
    for when, job in new_jobs:
        e = asyncio.Event()
        delta = datetime.fromtimestamp(when).astimezone(tz=tz) - datetime.now(tz=tz)
        # We need to create function here to capture the lexical context of
        # the parameters
        scheduled_test = ScheduledJob(
            job=job,
            when=when,
            event=e,
            dry_run=dry_run,
        )
        # We need to call the lambda here because the coroutine needs to be
        # created when the test is launched, otherwise no one is awaiting it
        # and python complains.
        h = loop.call_later(
            delta / timedelta(seconds=1),
            functools.partial(job.__call__, dry_run=dry_run),
        )
        tasks[generation].append((scheduled_test, h))
    return new_jobs[-1][0]


def show_scheduled_jobs_info(
    scheduled_jobs: Dict[int, List[ScheduledJobHandle]], gen: int, tz: timezone
) -> None:
    """
    Show information for the next tests scheduled.
    """
    if not scheduled_jobs.get(gen, []):
        log.info("[scheduler] No tests scheduled yet")
        return
    log.info("[scheduler] Next tests scheduled:")
    for scheduled_test, _ in scheduled_jobs.get(gen, []):
        if not scheduled_test.event.is_set():
            when = cron_date(timestamp=scheduled_test.when, tz=tz)
            log.info(
                "[scheduler]  * [%s] %s at %s",
                scheduled_test.id,
                scheduled_test.job.name,
                when,
            )


async def run_scheduler(
    scheduler_queue: "asyncio.Queue[Set[Job]]",
    tz: timezone,
    *,
    scheduled_jobs_size: int = 32,
    dry_run: bool = False,
    stop: Optional[asyncio.Event] = None
) -> None:
    """
    Get new TestPlan and add new tests into the runner queue with tests.
    Every time it gets a new test plan it checks if there are changes.

    It case of changes in the test plan, a new test generation is created and the current
    scheduled tests are cancelled. After this the new tests are scheduled in batches
    (at least SCHEDULED_TESTS_SIZE, defined in ctx, will be scheduled)

    When there are not changes in the test plan, it will just wait for completed tests
    and new tests will be scheduled (same amount of tests as completed).
    """
    defined_jobs: Optional[Set[Job]] = None
    scheduled_jobs: Dict[int, List[ScheduledJobHandle]] = {}
    generation = 0
    last_job_time = None
    last_scheduled_info = datetime.now()
    last_scheduled_delay = 3600
    while stop is None or not stop.is_set():
        try:
            # Remove completed tests
            remove_completed_jobs(generation, scheduled_jobs)
            event: Set[Job] = await asyncio.wait_for(scheduler_queue.get(), timeout=10)
            new_jobs = set(job for job in event)
            if (defined_jobs and defined_jobs != new_jobs) or not defined_jobs:
                # cancel now old tests
                cancel_old_jobs(generation, scheduled_jobs)
                defined_jobs = {job for job in event if job.enabled}
                del scheduled_jobs[generation]
                generation = generation + 1
                scheduled_jobs[generation] = []
                last_job_time = None
            else:
                if (
                    datetime.now() - last_scheduled_info
                ).seconds > last_scheduled_delay:
                    show_scheduled_jobs_info(
                        scheduled_jobs=scheduled_jobs, gen=generation, tz=tz
                    )
                    last_scheduled_info = datetime.now()
        except asyncio.TimeoutError:
            pass
        total_tests = sum(1 for scheduled_test, _ in scheduled_jobs[generation])
        num_active_jobs = sum(
            1
            for scheduled_test, _ in scheduled_jobs[generation]
            if not scheduled_test.event.is_set()
        )
        log.debug(
            "[scheduler] Number of active tests: %d/%d", num_active_jobs, total_tests
        )
        free_slots = scheduled_jobs_size - num_active_jobs
        log.debug("[scheduler] Number of free slots: %d", free_slots)
        if free_slots > 0 and defined_jobs:
            # we did not update the generation, keep queueing tests,
            last_job_time = schedule_jobs(
                tasks=scheduled_jobs,
                jobs=defined_jobs,
                n=free_slots,
                generation=generation,
                tz=tz,
                offset=last_job_time,
                dry_run=dry_run,
            )
            show_scheduled_jobs_info(
                scheduled_jobs=scheduled_jobs, gen=generation, tz=tz
            )


class Scheduler:
    def __init__(self, tz: Optional[timezone] = None) -> None:
        self._jobs_queue: "Optional[asyncio.Queue[Set[Job]]]" = None
        self._tz = tz if tz is not None else timezone.utc
        self._stop_event: Optional[asyncio.Event] = None
        self._scheduler_future: Optional["asyncio.Future[None]"] = None

    async def _run(self) -> None:
        await run_scheduler(self._jobs_queue, self._tz, stop=self._stop_event)

    def start(self) -> None:
        assert self._jobs_queue is None
        assert self._stop_event is None
        self._jobs_queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._scheduler_future = asyncio.ensure_future(self._run())

    def stop(self) -> None:
        assert self._stop_event is not None
        self._stop_event.set()

    async def wait(self) -> None:
        assert self._scheduler_future is not None
        await self._scheduler_future
        self._stop_event = None
        self._scheduler_future = None
        self._jobs_queue = None

    async def update_jobs(self, jobs: Set[Job]) -> None:
        assert self._jobs_queue is not None
        await self._jobs_queue.put(jobs)

    async def __aenter__(self) -> 'Scheduler':
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
        await self.wait()

    @property
    def running(self) -> bool:
        return self._scheduler_future is not None and not self._scheduler_future.done()
