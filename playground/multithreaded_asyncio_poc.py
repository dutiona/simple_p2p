import asyncio
import threading
import itertools
import concurrent.futures
from time import perf_counter
import numpy as np


async def spawn_task_and_run(loop, *coros):
    tasks = [
        loop.create_task(coro)
        for coro in coros
    ]
    return await asyncio.gather(*tasks)


async def tag_coro(tag, coro):
    ret = await coro
    return (tag, ret)


async def spawn_tagged_task_and_run(loop, *coros_tagged):
    tasks = [
        loop.create_task(tag_coro(tag, coro))
        for tag, coro in coros_tagged
    ]
    return await asyncio.gather(*tasks)


def coro_runner(*coros):
    thread_loop = asyncio.new_event_loop()
    result = thread_loop.run_until_complete(
        spawn_task_and_run(thread_loop, *coros))
    thread_loop.close()
    return result


def tagged_coro_runner(*coros_tagged):
    thread_loop = asyncio.new_event_loop()
    result = thread_loop.run_until_complete(
        spawn_tagged_task_and_run(thread_loop, *coros_tagged))
    thread_loop.close()
    return result


async def schedule_coros_in_executor_pool(max_workers, *coros):
    executor_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers)

    coro_buckets = []

    if len(coros) <= max_workers:
        coro_buckets = [[coro] for coro in coros]
    else:
        coro_buckets = np.array_split(coros, max_workers)

    main_loop = asyncio.get_running_loop()
    blocking_tasks = [
        main_loop.run_in_executor(
            executor_pool, coro_runner, *coros_bundle)
        for coros_bundle in coro_buckets
    ]

    completed, pending = await asyncio.wait(blocking_tasks)
    results = [t.result() for t in completed]
    # flatten result bucketing
    result_flatten = list(itertools.chain(*results))

    return result_flatten


# This scheduler tracks the result of each coroutine
# by a given key associated to a coro as an input dict
async def schedule_coros_dict_in_executor_pool(max_workers, **coros):
    executor_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers)

    tagged_coro_buckets = []

    if len(coros) <= max_workers:
        tagged_coro_buckets = [(key, coro) for key, coro in coros.items()]
    else:
        tagged_coro_buckets = np.array_split(list(coros.items()), max_workers)

    main_loop = asyncio.get_running_loop()
    blocking_tasks = [
        main_loop.run_in_executor(
            executor_pool, tagged_coro_runner, *tagged_coros_bundle)
        for tagged_coros_bundle in tagged_coro_buckets
    ]

    completed, pending = await asyncio.wait(blocking_tasks)
    results = [t.result() for t in completed]
    # flatten result bucketing
    result_flatten = list(itertools.chain(*results))

    return dict(result_flatten)  # convert list of tuple to dict


async def print_wait_and_return_coro(x, w):
    print("Executing in thread <{}> {} and waiting {}s...".format(
        threading.get_ident(), x, w))
    await asyncio.sleep(w)
    print("resuming...")
    return x


async def main():
    coros = [
        print_wait_and_return_coro(x, 1)
        for x in range(0, 15)
    ]
    max_workers = 5
    scheduler = schedule_coros_in_executor_pool(max_workers, *coros)
    results = await scheduler
    print(results)


async def main2():
    coros_dict = {}

    for x in range(0, 15):
        coros_dict[str(x)] = print_wait_and_return_coro(x, 1)

    max_workers = 5
    scheduler = schedule_coros_dict_in_executor_pool(max_workers, **coros_dict)
    results = await scheduler
    print(results)

if __name__ == '__main__':
    start = perf_counter()
    asyncio.run(main())
    end = perf_counter()
    duration_s = end - start
    # the print below proves that all threads are waiting its tasks asynchronously
    print(f'duration_s={duration_s:.3f}')

    start = perf_counter()
    asyncio.run(main2())
    end = perf_counter()
    duration_s = end - start
    # the print below proves that all threads are waiting its tasks asynchronously
    print(f'duration_s={duration_s:.3f}')
