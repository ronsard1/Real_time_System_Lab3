"""
timing_overhead.py - dispatch-latency measurement (step 9).

200 times: take a timestamp, start a thread whose only job is event.set(), and take a second
timestamp when event.wait() returns in the main thread. The interval covers thread creation,
scheduling of the new task, and waking the waiting task - an analogy to interrupt/dispatch
latency. The maximum is the worst-case observed dispatch latency.

    python timing_overhead.py [--iterations 200]
"""
import argparse
import statistics
import threading
import time


def measure(iterations=200):
    out = []
    for _ in range(iterations):
        ev = threading.Event()
        t0 = time.perf_counter()
        th = threading.Thread(target=ev.set)
        th.start()
        ev.wait()
        out.append(time.perf_counter() - t0)
        th.join()
    return out


def p95(xs):
    s = sorted(xs)
    return s[int(round(0.95 * (len(s) - 1)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=200)
    a = ap.parse_args()
    us = [1e6 * x for x in measure(a.iterations)]
    print(f"dispatch latency over {a.iterations} iterations (microseconds): min {min(us):.1f}  "
          f"mean {statistics.mean(us):.1f}  median {statistics.median(us):.1f}  p95 {p95(us):.1f}  "
          f"max (worst-case observed) {max(us):.1f}")


if __name__ == "__main__":
    main()
