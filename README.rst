Lightweight scheduler for python asyncio

Based on croniter to support the crontab syntax.

============
Installation
============

Installing acron.

.. code:: shell

    $ pip install acron

=====
Usage
=====

To get started you need at least one job.
Use the top level ``acron.run`` function for simple scheduling.


.. code:: python

    import asyncio
    import acron

    async def do_the_thing():
        print("Doing the thing")

    do_thing = Job(
        name="Do the thing",
        schedule="0/1 * * * *",
        func=do_the_thing,
    )

    if __name__ == "__main__":
        try:
            asyncio.run(acron.run({do_thing}))
        except KeyboardInterrupt:
            print("Bye.")


For more advanced use cases, the ``Scheduler`` class can be used as async context manager.
Call ``scheduler.wait()`` to keep it running forever.
To submit jobs call ``scheduler.update_jobs(jobs)`` with the complete set of jobs.

Running a simple example running a function every hour...


.. code:: python

    import asyncio

    from acron.scheduler import Scheduler, Job

    async def do_the_thing():
        print("Doing the thing")

    async def run_jobs_forever():
        do_thing = Job(
            name="Do the thing",
            schedule="0/1 * * * *",
            func=do_the_thing,
        )

        async with Scheduler() as scheduler:
            await scheduler.update_jobs({do_thing})
            await scheduler.wait()

    if __name__ == "__main__":
        try:
            asyncio.run(run_jobs_forever())
        except KeyboardInterrupt:
            print("Bye.")




Specifying a timezone.
----------------------

For python 3.9+ you can use the standard library's ``zoneinfo`` module to specify a timezone.

.. code:: python

    import zoneinfo

    async with Scheduler(tz=zoneinfo.ZoneInfo("Europe/Berlin")) as scheduler:
        ...



For earlier python versions you can use a third party library like ``pytz``.

.. code:: python

    import pytz

    async with Scheduler(tz=pytz.timezone("Europe/Berlin")) as scheduler:
        ...

=================
Local development
=================

The project uses poetry to run the test, the linter and to build the artifacts.

The easiest way to start working on acron is to use docker with the dockerfile
included in the repository (manual usage of poetry is explained here:
https://python-poetry.org/docs/ ).

To use docker, first generate the docker image. Run this command from the top
level directory in the repository:

.. code-block:: console

   docker build -t acron-builder -f docker/Dockerfile .

Now you can use it to build or run the linter/tests:

.. code-block:: console

    $ alias acron-builder="docker run --rm -it -v $PWD/dist:/build/dist acron-builder"

    $ acron-builder run pytest tests
    =============================================================================================== test session starts ================================================================================================
    platform linux -- Python 3.9.7, pytest-5.4.3, py-1.10.0, pluggy-0.13.1
    rootdir: /build
    plugins: asyncio-0.15.1
    collected 4 items
    tests/test_acron.py ....                                                                                                                                                                                     [100%]
    ================================================================================================ 4 passed in 0.04s =================================================================================================

    $ acron-builder build
    Building acron (0.1.0)
      - Building sdist
      - Built acron-0.1.0.tar.gz
      - Building wheel
      - Built acron-0.1.0-py3-none-any.whl

    $ ls dist
    acron-0.1.0-py3-none-any.whl  acron-0.1.0.tar.gz


=========
Debugging
=========

Debug logging can be enabled by setting the ``ACRON_DEBUG`` environment variable to ``TRUE``.

