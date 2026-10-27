"""
livelock_demo.py - two tasks, two locks, opposite acquisition order, polite back-off (lab task 3).

Each task must complete WORK units; one unit needs both locks. A task takes its first lock,
then TRIES (non-blocking) to take the second. If that fails it releases the first lock and
retries. T1 takes A then B, T2 takes B then A.

Lock-step mode: a barrier keeps the two tasks in step, which is the worst case. In every
round each task holds exactly the lock the other one needs, both back off at the same moment,
retry at the same moment and collide again. Both stay busy (the retry counters keep growing)
but no work unit is ever completed: a livelock (Section 3.8).

Randomised mode (the fix): the same code, but each back-off waits a random time, which
breaks the symmetry so one task soon gets both locks.

    python livelock_demo.py [--rounds 2000] [--work 50]
"""
import argparse
import random
import threading
import time


def run(rounds=2000, work=50, randomized=False, seed=0):
    lock_a, lock_b = threading.Lock(), threading.Lock()
    barrier = threading.Barrier(2)
    retries = {"T1": 0, "T2": 0}
    completed = {"T1": 0, "T2": 0}
    rng = random.Random(seed)

    def task(name, first, second):
        for _ in range(rounds):
            if completed[name] >= work:
                return
            if not randomized:
                barrier.wait()                       # lock-step: both start the round together
            with first:
                if not randomized:
                    barrier.wait()                   # both now hold their first lock
                else:
                    time.sleep(0.0002)               # some work while holding the first lock
                got = second.acquire(blocking=False)
                if not randomized:
                    barrier.wait()                   # both have tried before either lets go
                if got:
                    completed[name] += 1             # forward progress: both locks held
                    second.release()
                    continue
                retries[name] += 1                   # polite back-off: release first lock and retry
            if randomized:
                time.sleep(rng.uniform(0, 0.001))    # random back-off breaks the symmetry
            else:
                barrier.wait()                       # both have released; next round

    t1 = threading.Thread(target=task, args=("T1", lock_a, lock_b))
    t2 = threading.Thread(target=task, args=("T2", lock_b, lock_a))
    t0 = time.perf_counter()
    t1.start(); t2.start(); t1.join(); t2.join()
    return retries, completed, time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2000)
    ap.add_argument("--work", type=int, default=50)
    a = ap.parse_args()
    r, c, dt = run(a.rounds, a.work, randomized=False)
    print(f"lock-step back-off : {a.rounds} rounds in {dt:.2f}s, retries T1={r['T1']} T2={r['T2']}, "
          f"work units done T1={c['T1']}/{a.work} T2={c['T2']}/{a.work}  -> LIVELOCK (busy, no progress)")
    r, c, dt = run(a.rounds, a.work, randomized=True)
    print(f"random back-off    : finished in {dt:.2f}s, retries T1={r['T1']} T2={r['T2']}, "
          f"work units done T1={c['T1']}/{a.work} T2={c['T2']}/{a.work}")


if __name__ == "__main__":
    main()
