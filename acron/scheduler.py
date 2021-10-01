import asyncio
import dataclasses
import functools
import itertools
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Set, Optional, Callable, Awaitable

from croniter import croniter

__all__ = [
    "Job",
    "Scheduler",
    "ScheduledJob",
]


log = logging.getLogger("acron")


def enable_acron_debug_logs():
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.DEBUG)


def cron_date(timestamp: float, tz: timezone) -> str:
    fmt = "%Y-%m-%d %H:%M:%S %Z%z"
    return datetime.fromtimestamp(timestamp).astimezone(tz=tz).strftime(fmt)


@dataclasses.dataclass(frozen=True)
class Job:
    name: str
    schedule: str
    enabled: bool
    func: Callable[[], Awaitable[None]]


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
    Compute the n first jobs needed to be scheduled.
    If offset is defined then the jobs computed will be those that need to run after that time.
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
    Cancel all the scheduled jobs.
    """
    for scheduled_job, hs in tasks.get(generation, []):
        scheduled_job.event.set()
        hs.cancel()


def remove_completed_jobs(gen: int, tasks: Dict[int, List[ScheduledJobHandle]]) -> None:
    """
    Removes the scheduled jobs already completed.
    """
    xs = []
    for scheduled_job, hs in tasks.get(gen, []):
        if scheduled_job.event.is_set():
            continue
        xs.append((scheduled_job, hs))
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
    Schedule the next jobs from the defined jobs.
    It returns the timestamp for the last job scheduled.
    """
    loop = asyncio.get_running_loop()
    new_jobs = croniter_sort_jobs(jobs, tz, n, offset)
    for when, job in new_jobs:
        e = asyncio.Event()
        delta = datetime.fromtimestamp(when).astimezone(tz=tz) - datetime.now(tz=tz)
        # We need to create function here to capture the lexical context of
        # the parameters
        scheduled_job = ScheduledJob(
            job=job,
            when=when,
            event=e,
            dry_run=dry_run,
        )
        # We need to call the lambda here because the coroutine needs to be
        # created when the job is launched, otherwise no one is awaiting it
        # and python complains.
        h = loop.call_later(
            delta / timedelta(seconds=1),
            lambda f: asyncio.ensure_future(job.func()),
        )
        tasks[generation].append((scheduled_job, h))
    return new_jobs[-1][0]


def show_scheduled_jobs_info(
    scheduled_jobs: Dict[int, List[ScheduledJobHandle]], gen: int, tz: timezone
) -> None:
    """
    Show information for the next jobs scheduled.
    """
    if not scheduled_jobs.get(gen, []):
        log.info("[scheduler] No jobs scheduled yet")
        return
    log.info("[scheduler] Next jobs scheduled:")
    for scheduled_job, _ in scheduled_jobs.get(gen, []):
        if not scheduled_job.event.is_set():
            when = cron_date(timestamp=scheduled_job.when, tz=tz)
            log.info(
                "[scheduler]  * [%s] %s at %s",
                scheduled_job.id,
                scheduled_job.job.name,
                when,
            )


class Scheduler:
    def __init__(
        self, tz: Optional[timezone] = None, *, now: Optional[datetime] = None
    ) -> None:
        self._jobs_queue: "Optional[asyncio.Queue[Set[Job]]]" = None
        self._tz = tz if tz is not None else timezone.utc
        self._stop_event: Optional[asyncio.Event] = None
        self._scheduler_future: Optional["asyncio.Future[None]"] = None
        self._defined_jobs: Optional[Set[Job]] = None
        self._scheduled_jobs: Dict[int, List[ScheduledJobHandle]] = {}
        self._scheduled_jobs_size = 32
        self._generation = 0
        self._last_job_time: Optional[float] = None
        self._last_scheduled_info = now or datetime.now()
        self._last_scheduled_delay = 3600
        self._dry_run = False

    def process_jobs_update(
        self, new_jobs: Set[Job], *, now: Optional[datetime] = None
    ) -> None:
        if now is None:
            now = datetime.now()
        if (
            self._defined_jobs and self._defined_jobs != new_jobs
        ) or not self._defined_jobs:
            cancel_old_jobs(self._generation, self._scheduled_jobs)
            self._defined_jobs = {job for job in new_jobs if job.enabled}
            if self._generation > 0:
                del self._scheduled_jobs[self._generation]
            self._generation = self._generation + 1
            self._scheduled_jobs[self._generation] = []
            self._last_job_time = None
        else:
            if (now - self._last_scheduled_info).seconds > self._last_scheduled_delay:
                show_scheduled_jobs_info(
                    scheduled_jobs=self._scheduled_jobs,
                    gen=self._generation,
                    tz=self._tz,
                )
                self._last_scheduled_info = now

    def schedule_jobs(self) -> None:
        total_jobs = sum(
            1 for scheduled_job, _ in self._scheduled_jobs[self._generation]
        )
        num_active_jobs = sum(
            1
            for scheduled_job, _ in self._scheduled_jobs[self._generation]
            if not scheduled_job.event.is_set()
        )
        log.debug(
            "[scheduler] Number of active jobs: %d/%d", num_active_jobs, total_jobs
        )
        free_slots = self._scheduled_jobs_size - num_active_jobs
        log.debug("[scheduler] Number of free slots: %d", free_slots)
        if free_slots > 0 and self._defined_jobs:
            # we did not update the generation, keep queueing jobs,
            self._last_job_time = schedule_jobs(
                tasks=self._scheduled_jobs,
                jobs=self._defined_jobs,
                n=free_slots,
                generation=self._generation,
                tz=self._tz,
                offset=self._last_job_time,
                dry_run=self._dry_run,
            )
            show_scheduled_jobs_info(
                scheduled_jobs=self._scheduled_jobs, gen=self._generation, tz=self._tz
            )

    def scheduled_jobs(self) -> List[ScheduledJob]:
        return [
            scheduled_job for scheduled_job, _ in self._scheduled_jobs[self._generation]
        ]

    async def _run(self) -> None:
        assert self._stop_event is not None
        assert self._jobs_queue is not None
        while not self._stop_event.is_set():
            remove_completed_jobs(self._generation, self._scheduled_jobs)
            # Wait for new jobs, make sure we don't wait the whole timeout if stopped
            get_future = asyncio.ensure_future(self._jobs_queue.get())
            stop_future = asyncio.ensure_future(self._stop_event.wait())
            done, pending = await asyncio.wait(
                (get_future, stop_future),
                timeout=10.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for future in pending:
                future.cancel()
            for future in done:
                if future == get_future:
                    jobs = get_future.result()
                    self.process_jobs_update(jobs)
            self.schedule_jobs()

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

    async def __aenter__(self) -> "Scheduler":
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
        await self.wait()

    @property
    def running(self) -> bool:
        return self._scheduler_future is not None and not self._scheduler_future.done()
