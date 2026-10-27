"""
race_demo.py - lost-update race condition (Mini Project 3.1, steps 1-3).

Five threads (RTOS tasks) each increment an unprotected shared counter 1000 times.
Each increment is a non-atomic read -> sleep -> write sequence; the sleep widens the
window in which another task can read the same old value, so updates are lost.

    python race_demo.py [--threads 5] [--iterations 1000] [--runs 3]
"""
import argparse
import threading
import time

shared_counter = 0          # module-scope shared state, deliberately NOT protected


def increment_unsafe(iterations):
    global shared_counter
    for _ in range(iterations):
        value = shared_counter          # read
        time.sleep(0.0001)              # widen the interleaving window (another task may run here)
        shared_counter = value + 1      # write back: overwrites any update made meanwhile


def run_once(n_threads, iterations):
    global shared_counter
    shared_counter = 0
    threads = [threading.Thread(target=increment_unsafe, args=(iterations,)) for _ in range(n_threads)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return shared_counter, time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=5)
    ap.add_argument("--iterations", type=int, default=1000)
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    expected = a.threads * a.iterations
    for r in range(1, a.runs + 1):
        final, dt = run_once(a.threads, a.iterations)
        lost = expected - final
        print(f"race_demo  run {r}: threads={a.threads} final={final} expected={expected} "
              f"lost={lost} ({100 * lost / expected:.1f}%) time={dt:.2f}s")


if __name__ == "__main__":
    main()
