"""
run_experiments.py - Mini Project 3.2 driver.

1. Flawed lock order: reproduce the deadlock (watchdog message + lock-wait snapshot), 5 trials,
   plus a check of how often it appears without the hold window.
2. Corrected lock order: the same load, confirm the watchdog never fires.
3. Throughput and blocking time of the corrected version across buffer capacities.

    python Mini_Project_3_2_Deadlock_Buffer/run_experiments.py
"""
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bounded_buffer import Config, run  # noqa: E402

FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)
LOG = []


def say(s=""):
    print(s, flush=True)
    LOG.append(s)


# ------------------------------------------------------------------ 1. deadlock reproduction
say("=" * 78)
say("1. FLAWED version: producers buffer_lock -> stats_lock, consumers stats_lock -> buffer_lock")
say("   3 producers, 3 consumers, capacity 5, 20000 items, 0.1 ms work while holding the first lock")
dead_times = []
for i in range(5):
    r = run(Config(lock_order="flawed", hold_ms=0.1, total_items=20000, seed=i + 1))
    say(f"   trial {i + 1}: deadlocked={r.deadlocked}  produced={r.produced} consumed={r.consumed}  "
        f"last progress at t={r.time_to_deadlock_s:.3f} s" if r.deadlocked else
        f"   trial {i + 1}: completed without deadlock")
    if r.deadlocked:
        dead_times.append(r.time_to_deadlock_s)
    if i == 0:
        say("   " + r.watchdog_msg)
        say("   lock-wait snapshot:")
        for line in r.snapshot:
            say("      " + line)
say(f"   deadlocked in {len(dead_times)}/5 trials")

say("   Same flawed code WITHOUT the hold window (hold_ms = 0), 10 trials of 3000 items:")
n_dead = 0
for i in range(10):
    r = run(Config(lock_order="flawed", hold_ms=0.0, total_items=3000, seed=i + 1))
    n_dead += r.deadlocked
    say(f"   trial {i + 1}: {'DEADLOCK at t=%.3f s' % r.time_to_deadlock_s if r.deadlocked else 'completed'}"
        f" (consumed {r.consumed})")
say(f"   deadlocked in {n_dead}/10 trials without the hold window")

# ------------------------------------------------------------------ 2. fix
say("=" * 78)
say("2. CORRECTED version: every task takes buffer_lock -> stats_lock (same load, hold 0.1 ms)")
for i in range(5):
    r = run(Config(lock_order="fixed", hold_ms=0.1, total_items=20000, seed=i + 1))
    say(f"   trial {i + 1}: deadlocked={r.deadlocked} consumed={r.consumed}/20000 in {r.elapsed_s:.2f} s "
        f"({r.throughput:.0f} items/s), watchdog {'FIRED' if r.deadlocked else 'silent'}")

# ------------------------------------------------------------------ 3. capacity sweep
say("=" * 78)
say("3. Corrected version, capacity sweep: 3 P / 3 C, 3000 items, mean 1 ms produce and 1 ms consume "
    "(exponential), 3 runs each")
caps = [1, 2, 5, 10, 25, 50]
rows = []
for cap in caps:
    rs = [run(Config(lock_order="fixed", capacity=cap, total_items=3000, seed=s)) for s in (1, 2, 3)]
    assert not any(r.deadlocked for r in rs)
    thr = [r.throughput for r in rs]
    pw = [r.producer_wait_ms for r in rs]
    cw = [r.consumer_wait_ms for r in rs]
    row = {"capacity": cap, "throughput_mean": statistics.mean(thr), "throughput_sd": statistics.stdev(thr),
           "producer_wait_ms": statistics.mean(pw), "consumer_wait_ms": statistics.mean(cw),
           "elapsed_s": statistics.mean(r.elapsed_s for r in rs)}
    rows.append(row)
    say(f"   capacity {cap:3d}: throughput {row['throughput_mean']:7.0f} +/- {row['throughput_sd']:4.0f} items/s, "
        f"producer wait {row['producer_wait_ms']:6.3f} ms/item, consumer wait {row['consumer_wait_ms']:6.3f} ms/item, "
        f"run time {row['elapsed_s']:.2f} s")
with open(os.path.join(HERE, "results_3_2_capacity.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

fig, ax = plt.subplots(figsize=(7.5, 4))
ax.errorbar(caps, [r["throughput_mean"] for r in rows], yerr=[r["throughput_sd"] for r in rows],
            fmt="o-", capsize=3, label="throughput (items/s)")
ax.set_xscale("log")
ax.set_xticks(caps)
ax.set_xticklabels([str(c) for c in caps])
ax.set_xlabel("buffer capacity (log scale)")
ax.set_ylabel("throughput (items/s)")
ax.grid(alpha=0.35, which="both")
ax2 = ax.twinx()
ax2.plot(caps, [r["producer_wait_ms"] for r in rows], "s--", color="#d62728", label="producer wait (ms/item)")
ax2.plot(caps, [r["consumer_wait_ms"] for r in rows], "^--", color="#2ca02c", label="consumer wait (ms/item)")
ax2.set_ylabel("mean blocking time per item (ms)")
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="center right")
ax.set_title("Corrected buffer: throughput and blocking time versus capacity (3 runs each)", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_throughput_vs_capacity.png"), dpi=160)
plt.close(fig)

with open(os.path.join(HERE, "results_3_2.txt"), "w") as f:
    f.write("\n".join(LOG) + "\n")
print("results written to results_3_2.txt and results_3_2_capacity.csv; figure in", FIG)
