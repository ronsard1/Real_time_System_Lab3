"""
semaphore_pool.py - counting semaphore guarding a pool of identical resource blocks (steps 7-8).

threading.Semaphore(3) stands for three fixed-size memory blocks. Eight tasks acquire a
block, hold it for a random short time, and release it. The script records each task's wait
time and the maximum number of simultaneous holders.

    python semaphore_pool.py [--count 3] [--tasks 8] [--seed 1]
"""
import argparse
import random
import threading
import time


def run(count=3, tasks=8, seed=1, hold_range=(0.02, 0.06)):
    rng = random.Random(seed)
    holds = [rng.uniform(*hold_range) for _ in range(tasks)]       # fixed per task for repeatability
    pool_semaphore = threading.Semaphore(count)
    meta = threading.Lock()                                         # protects the two counters below
    state = {"holders": 0, "max_holders": 0}
    waits = [0.0] * tasks
    start = threading.Barrier(tasks)                                # all tasks request at the same instant

    def task(i):
        start.wait()
        t_req = time.perf_counter()
        pool_semaphore.acquire()                                    # blocks while all blocks are taken
        waits[i] = time.perf_counter() - t_req
        with meta:
            state["holders"] += 1
            state["max_holders"] = max(state["max_holders"], state["holders"])
        time.sleep(holds[i])                                        # use the resource
        with meta:
            state["holders"] -= 1
        pool_semaphore.release()

    th = [threading.Thread(target=task, args=(i,)) for i in range(tasks)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    return waits, state["max_holders"], holds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--tasks", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    waits, mx, holds = run(a.count, a.tasks, a.seed)
    for i, (w, h) in enumerate(zip(waits, holds)):
        print(f"  task {i}: hold {1000 * h:5.1f} ms, waited {1000 * w:6.1f} ms")
    nz = sum(w > 0.001 for w in waits)
    print(f"Semaphore({a.count}): max simultaneous holders = {mx}; tasks that waited = {nz}/{a.tasks}; "
          f"mean wait = {1000 * sum(waits) / len(waits):.1f} ms; max wait = {1000 * max(waits):.1f} ms")


if __name__ == "__main__":
    main()
