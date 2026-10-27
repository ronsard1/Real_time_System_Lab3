"""
bounded_buffer.py - multi-producer / multi-consumer bounded buffer with two explicit locks
(Mini Project 3.2).

Shared state
  buffer      : a Python list holding at most CAPACITY items, guarded by buffer_lock
  stats       : dict of counters (produced, consumed, producer/consumer wait time), guarded by stats_lock

Each producer and each consumer must update BOTH the buffer and the statistics in the same
critical step, so every step needs both locks. The only thing that changes between the
flawed and the corrected version is the ORDER in which consumers take the two locks:

  flawed    : producers  buffer_lock -> stats_lock      consumers  stats_lock -> buffer_lock
  corrected : producers  buffer_lock -> stats_lock      consumers  buffer_lock -> stats_lock

A watchdog thread samples the produced/consumed counters; if neither changes for
`stall_s` seconds while work is still outstanding, it declares a deadlock and prints a
lock-wait snapshot (which lock every task holds and which one it is waiting for).

All tasks are daemon threads, so a deadlocked run ends when the watchdog reports it;
no manual kill is needed.
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field


@dataclass
class Config:
    capacity: int = 5            # bounded-buffer size
    producers: int = 3
    consumers: int = 3
    total_items: int = 3000      # items produced in total (split across producers)
    produce_ms: float = 1.0      # mean work per item outside the locks (exponential)
    consume_ms: float = 1.0
    hold_ms: float = 0.0         # time spent holding the FIRST lock before taking the second
    poll_ms: float = 0.2         # back-off when the buffer is full (producer) or empty (consumer)
    lock_order: str = "fixed"    # "flawed" or "fixed"
    stall_s: float = 2.0         # watchdog: no progress for this long = deadlock
    seed: int = 1


@dataclass
class Result:
    deadlocked: bool
    elapsed_s: float
    produced: int
    consumed: int
    throughput: float                    # items consumed per second
    producer_wait_ms: float              # mean wait per item for buffer space
    consumer_wait_ms: float              # mean wait per item for an available item
    snapshot: list = field(default_factory=list)
    watchdog_msg: str = ""
    time_to_deadlock_s: float | None = None


def run(cfg: Config, verbose: bool = False) -> Result:
    buffer: list = []
    buffer_lock = threading.Lock()
    stats_lock = threading.Lock()
    stats = {"produced": 0, "consumed": 0, "p_wait": 0.0, "c_wait": 0.0}

    # lock-wait bookkeeping for the snapshot (written by each task about itself only)
    status: dict[str, dict] = {}
    names = {id(buffer_lock): "buffer_lock", id(stats_lock): "stats_lock"}

    def acquire(me, lock):
        status[me]["waiting"] = names[id(lock)]
        lock.acquire()
        status[me]["waiting"] = None
        status[me]["holding"].append(names[id(lock)])

    def release(me, lock):
        lock.release()
        status[me]["holding"].remove(names[id(lock)])

    per_producer = [cfg.total_items // cfg.producers + (1 if i < cfg.total_items % cfg.producers else 0)
                    for i in range(cfg.producers)]
    done = threading.Event()

    def producer(idx):
        me = f"P{idx}"
        rng = random.Random(cfg.seed * 100 + idx)
        status[me] = {"holding": [], "waiting": None, "role": "producer"}
        for k in range(per_producer[idx]):
            time.sleep(rng.expovariate(1000.0 / cfg.produce_ms))       # produce the item
            t_start = time.perf_counter()
            while True:
                acquire(me, buffer_lock)                               # producers: buffer then stats
                if cfg.hold_ms:
                    time.sleep(cfg.hold_ms / 1000)
                acquire(me, stats_lock)
                if len(buffer) < cfg.capacity:
                    waited = time.perf_counter() - t_start
                    buffer.append((me, k))
                    stats["produced"] += 1
                    stats["p_wait"] += waited
                    release(me, stats_lock)
                    release(me, buffer_lock)
                    break
                release(me, stats_lock)                                # full: back off and retry
                release(me, buffer_lock)
                time.sleep(cfg.poll_ms / 1000)

    def consumer(idx):
        me = f"C{idx}"
        rng = random.Random(cfg.seed * 1000 + idx)
        status[me] = {"holding": [], "waiting": None, "role": "consumer"}
        first, second = ((stats_lock, buffer_lock) if cfg.lock_order == "flawed"
                         else (buffer_lock, stats_lock))
        while True:
            t_start = time.perf_counter()
            got = None
            while True:
                acquire(me, first)                                     # flawed: stats first!
                if cfg.hold_ms:
                    time.sleep(cfg.hold_ms / 1000)
                acquire(me, second)
                if stats["consumed"] >= cfg.total_items:               # all work done
                    release(me, second)
                    release(me, first)
                    return
                if buffer:
                    got = buffer.pop(0)
                    stats["consumed"] += 1
                    stats["c_wait"] += time.perf_counter() - t_start
                    if stats["consumed"] >= cfg.total_items:
                        done.set()
                release(me, second)
                release(me, first)
                if got is not None:
                    break
                time.sleep(cfg.poll_ms / 1000)                         # empty: back off and retry
            time.sleep(rng.expovariate(1000.0 / cfg.consume_ms))       # consume the item

    threads = [threading.Thread(target=producer, args=(i,), daemon=True, name=f"P{i}")
               for i in range(cfg.producers)]
    threads += [threading.Thread(target=consumer, args=(i,), daemon=True, name=f"C{i}")
                for i in range(cfg.consumers)]

    result = {"deadlocked": False, "snapshot": [], "msg": "", "t_dead": None}

    def watchdog():
        last = (-1, -1)
        last_change = time.perf_counter()
        while not done.is_set():
            time.sleep(0.1)
            cur = (stats["produced"], stats["consumed"])                # read-only sample, no lock taken
            now = time.perf_counter()
            if cur != last:
                last, last_change = cur, now
            elif now - last_change >= cfg.stall_s:
                result["deadlocked"] = True
                result["t_dead"] = last_change - t0
                result["msg"] = (f"WATCHDOG: no progress for {cfg.stall_s:.1f} s "
                                 f"(produced={cur[0]}, consumed={cur[1]} of {cfg.total_items}) -> DEADLOCK")
                result["snapshot"] = [
                    f"{n}: holding {status[n]['holding'] or '-'}, waiting for {status[n]['waiting'] or '-'}"
                    for n in sorted(status)]
                done.set()
                return

    wd = threading.Thread(target=watchdog, daemon=True, name="watchdog")
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    wd.start()
    done.wait()
    if not result["deadlocked"]:
        for t in threads:
            t.join()
    elapsed = time.perf_counter() - t0
    if verbose and result["deadlocked"]:
        print(result["msg"])
        for line in result["snapshot"]:
            print("   ", line)
    p, c = stats["produced"], stats["consumed"]
    return Result(result["deadlocked"], elapsed, p, c,
                  c / elapsed if not result["deadlocked"] else 0.0,
                  1000 * stats["p_wait"] / max(p, 1), 1000 * stats["c_wait"] / max(c, 1),
                  result["snapshot"], result["msg"], result["t_dead"])
