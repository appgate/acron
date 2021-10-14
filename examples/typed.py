import asyncio
import dataclasses

import acron
from acron.scheduler import Scheduler
from acron.job import Job, SimpleJob, ScheduledJob


@dataclasses.dataclass(frozen=True)
class JobData:
    foo: bool


async def do_the_thing(data: JobData) -> None:
    print(f"Doing the thing: {data.foo}")


async def do_the_simple_thing() -> None:
    print("Doing the simple thing")


def show(scheduled_job: ScheduledJob[JobData]) -> str:
    return f"{scheduled_job.cron_date()} {scheduled_job.job.foo}"


async def run_jobs_forever():
    do_thing_1 = Job[JobData](
        name="Do the thing once a minute",
        schedule="0/1 * * * *",
        func=do_the_thing,
        data=JobData(True),
    )
    do_thing_2 = Job[JobData](
        name="Do the other thing once a minute",
        schedule="0/1 * * * *",
        func=do_the_thing,
        data=JobData(False),
    )
    do_simple_thing = SimpleJob(schedule="0/1 * * * *", func=do_the_simple_thing)

    await acron.run(jobs={do_thing_1, do_thing_2, do_simple_thing})


if __name__ == "__main__":
    try:
        asyncio.run(run_jobs_forever())
    except KeyboardInterrupt:
        print("Bye.")
