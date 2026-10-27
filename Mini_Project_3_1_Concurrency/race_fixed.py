"""
race_fixed.py - the same task set with the critical section protected by a mutex (step 4).

threading.Lock plays the role of an RTOS mutex: only one task at a time may execute the
read -> sleep -> write sequence, so no update can be lost.

    python race_fixed.py [--threads 5] [--iterations 1000] [--runs 3]
"""
import argparse
import threading
import time

shared_counter = 0
counter_lock = threading.Lock()     # mutex guarding shared_counter


def increment_safe(iterations):
    global shared_counter
    for _ in range(iterations):
        with counter_lock:                  # enter critical section (blocks if another task is inside)
            value = shared_counter
            time.sleep(0.0001)              # same widened window, but now nobody else can interleave
            shared_counter = value + 1
        # lock released here; other tasks may now enter


def run_once(n_threads, iterations):
    global shared_counter
    shared_counter = 0
    threads = [threading.Thread(target=increment_safe, args=(iterations,)) for _ in range(n_threads)]
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
        print(f"race_fixed run {r}: threads={a.threads} final={final} expected={expected} "
              f"{'OK' if final == expected else 'MISMATCH'} time={dt:.2f}s")


if __name__ == "__main__":
    main()
