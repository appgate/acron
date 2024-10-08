import asyncio
from zoneinfo import ZoneInfo

import acron


async def do_the_thing():
    print("Doing the thing")


async def run_jobs_forever():
    do_thing = acron.SimpleJob(
        name="Do the thing daily", schedule="14 13 * * *", func=do_the_thing
    )
    await acron.run({do_thing}, ZoneInfo("Europe/Berlin"))


if __name__ == "__main__":
    try:
        asyncio.run(run_jobs_forever())
    except KeyboardInterrupt:
        print("Bye.")
