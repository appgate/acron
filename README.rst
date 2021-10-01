Lightweight scheduler for python asyncio

Based on croniter to support the crontab syntax.


.. code:: python

    import asyncio

    from acron.scheduler import Scheduler, Job

    async def do_the_thing():
        print('Doing the thing')

    async def run_jobs_forever():
        stop = asyncio.Event()

        do_thing = Job(
            name="Do the thing",
            schedule="0/1 * * * *",
            func=do_the_thing,
        )

        async with Scheduler() as scheduler:
            await scheduler.update_jobs({do_thing})
            await stop.wait()

    if __name__ == '__main__':
        try:
            asyncio.run(run_jobs_forever())
        except KeyboardInterrupt:
            print('Bye.')
