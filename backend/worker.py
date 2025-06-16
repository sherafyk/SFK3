from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)


def run_async(func, *args, **kwargs):
    return executor.submit(func, *args, **kwargs)
