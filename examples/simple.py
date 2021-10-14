import asyncio

from acron.scheduler import Scheduler
from acron.job import SimpleJob


async def do_the_thing():
    print("Doing the thing")


async def run_jobs_forever():
    do_thing = SimpleJob(
        name="Do the thing once a minute", schedule="0/1 * * * *", func=do_the_thing
    )

    async with Scheduler() as scheduler:
        await scheduler.update_jobs({do_thing})
        await scheduler.wait()


if __name__ == "__main__":
    try:
        asyncio.run(run_jobs_forever())
    except KeyboardInterrupt:
        print("Bye.")
