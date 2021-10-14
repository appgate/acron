import asyncio
import dataclasses
import logging

import acron
from acron.job import Job, SimpleJob, job_context


@dataclasses.dataclass(frozen=True)
class JobData:
    foo: bool


async def do_the_thing(data: JobData) -> None:
    print(f"Doing the thing: {data.foo}")


async def do_the_simple_thing() -> None:
    print("Doing the simple thing")


def show(data: JobData) -> str:
    context = job_context()
    return f"thing is {data.foo} {context.scheduled_job.tz.utc}"


async def run_jobs_forever():
    do_thing_1 = Job[JobData](
        name="Do the thing once a minute",
        schedule="0/1 * * * *",
        show=show,
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

    acron.logger.setLevel(logging.INFO)
    acron.logger.addHandler(logging.StreamHandler())
    await acron.run(jobs={do_thing_1, do_thing_2, do_simple_thing})


if __name__ == "__main__":
    try:
        asyncio.run(run_jobs_forever())
    except KeyboardInterrupt:
        print("Bye.")
