import asyncio
import sys

if sys.version_info >= (3, 9):
    from zoneinfo import ZoneInfo
else:
    from pytz import timezone as ZoneInfo

from acron.scheduler import Scheduler, Job


async def do_the_thing():
    print("Doing the thing")


async def run_jobs_forever():
    do_thing = Job(name="Do the thing daily", schedule="11 12 * * *", func=do_the_thing)

    async with Scheduler(ZoneInfo("Europe/Stockholm")) as scheduler:
        await scheduler.update_jobs({do_thing})
        await scheduler.wait()


if __name__ == "__main__":
    try:
        asyncio.run(run_jobs_forever())
    except KeyboardInterrupt:
        print("Bye.")
