import asyncio
import functools

from acron.scheduler import Scheduler, Job


async def do_the_thing(when):
    print(f"Doing the thing: {when}")


async def run_jobs_forever():
    do_thing_every_minute = Job(
        name="Do the thing once a minute",
        schedule="0/1 * * * *",
        func=functools.partial(do_the_thing, "once a minute"),
    )
    do_thing_hourly = Job(
        name="Do the thing once an hour",
        schedule="0 */1 * * *",
        func=functools.partial(do_the_thing, "once an hour"),
    )
    do_thing_dayly = Job(
        name="Do the thing once a day",
        schedule="0 0 */1 * *",
        func=functools.partial(do_the_thing, "once a day"),
    )

    jobs = {do_thing_every_minute, do_thing_hourly, do_thing_dayly}
    async with Scheduler() as scheduler:
        await scheduler.update_jobs(jobs)
        await scheduler.wait()


if __name__ == "__main__":
    try:
        asyncio.run(run_jobs_forever())
    except KeyboardInterrupt:
        print("Bye.")
