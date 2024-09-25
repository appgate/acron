import asyncio
import contextvars
import dataclasses
import logging
import uuid
from dataclasses import dataclass, field
from datetime import timezone, datetime
import time
from typing import Optional, Callable, Awaitable, Generic, TypeVar, Tuple

__all__ = ["Job", "SimpleJob", "ScheduledJob", "JobContext", "job_context"]


log = logging.getLogger("acron")
TaskT = TypeVar("TaskT")


@dataclass(frozen=True)
class Job(Generic[TaskT]):
    schedule: str
    data: TaskT
    func: Callable[[TaskT], Awaitable[None]] = field(compare=False)
    show: Optional[Callable[[TaskT], str]] = field(default=None, compare=False)
    name: Optional[str] = None
    enabled: bool = True

    @staticmethod
    def simple(
        schedule: str,
        func: Callable[[], Awaitable[None]],
        *,
        show: Optional[Callable[[], str]] = None,
        name: Optional[str] = None,
        enabled: bool = True
    ) -> "Job[Tuple[()]]":
        return Job[Tuple[()]](
            schedule=schedule,
            func=lambda _: func(),
            data=(),
            name=name,
            show=lambda _: show() if show else "",
            enabled=enabled,
        )


SimpleJob = Job.simple


def cron_date(timestamp: float, tz: timezone) -> str:
    fmt = "%Y-%m-%d %H:%M:%S %Z%z"
    return datetime.fromtimestamp(timestamp).astimezone(tz=tz).strftime(fmt)


@dataclasses.dataclass(frozen=True)
class ScheduledJob(Generic[TaskT]):
    job: Job[TaskT]
    tz: timezone
    when: float
    dry_run: bool
    event: asyncio.Event = dataclasses.field(default_factory=asyncio.Event)
    id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    async def run(self) -> None:
        log.debug("[scheduler id=%s] Running scheduled job %s", self.id, self.job.name)
        start = time.monotonic()
        token = _job_context.set(JobContext(self))
        try:
            # mypy gets confused because we are calling a function but
            # it looks like we are calling a method.
            await self.job.func(self.job.data)  # type: ignore
        finally:
            _job_context.reset(token)
            self.event.set()
            log.debug(
                "[scheduler id=%s] Done running job %s after %.1f seconds",
                self.id,
                self.job.name,
                time.monotonic() - start,
            )

    @property
    def cron_date(self) -> str:
        return cron_date(timestamp=self.when, tz=self.tz)


@dataclasses.dataclass(frozen=True)
class JobContext:
    scheduled_job: ScheduledJob


_job_context: contextvars.ContextVar[JobContext] = contextvars.ContextVar(
    "acron_job_context"
)


def job_context() -> JobContext:
    return _job_context.get()
