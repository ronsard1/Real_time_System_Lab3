"""
run_all.py - runs every Mini Project 3.1 script and lab task, prints the results, and writes
results_3_1.txt plus the charts in figures/.

    python Mini_Project_3_1_Concurrency/run_all.py
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import race_demo, race_fixed, queue_sim, semaphore_pool, timing_overhead, livelock_demo  # noqa: E402

FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)
LOG = []


def say(s=""):
    print(s, flush=True)
    LOG.append(s)


say(f"Python {sys.version.split()[0]} on {sys.platform}, {os.cpu_count()} CPU(s)")

# ------------------------------------------------------------------ race condition, 5 and 10 threads
say("=" * 78)
say("Steps 1-4 and lab task 1: lost-update race, unprotected versus mutex-protected")
race = {}
for n in (5, 10):
    for name, mod in (("race_demo", race_demo), ("race_fixed", race_fixed)):
        runs = 5 if name == "race_demo" else 3
        vals = []
        for r in range(1, runs + 1):
            final, dt = mod.run_once(n, 1000)
            vals.append(final)
            say(f"  {name:10s} threads={n:2d} run {r}: final={final:5d} expected={n * 1000} "
                f"lost={n * 1000 - final:5d} ({100 * (n * 1000 - final) / (n * 1000):4.1f}%)  {dt:.2f}s")
        race[(name, n)] = vals

# ------------------------------------------------------------------ message queue
say("=" * 78)
say("Steps 5-6: bounded queue (maxsize 5, 20 items, producer work 2 ms per item), 3 runs each")
q_rows = []
for cd in (0.0, 0.006):
    rs = [queue_sim.run(5, 20, cd, 0.002) for _ in range(3)]
    for r in rs:
        say("  " + queue_sim.fmt(r))
    q_rows.append((cd, rs))
say("Lab task 4: average latency versus maxsize (slow consumer 6 ms/item, and fast consumer)")
sizes = [1, 2, 5, 10, 20]
sweep = {}
for cd in (0.0, 0.006):
    for m in sizes:
        rs = [queue_sim.run(m, 20, cd, 0.002) for _ in range(3)]
        avg = statistics.mean(r["lat_avg_ms"] for r in rs)
        mx = max(r["lat_max_ms"] for r in rs)
        blk = statistics.mean(r["blocked_puts"] for r in rs)
        sweep[(cd, m)] = (avg, mx, blk)
        say(f"  consumer_delay={1000 * cd:3.0f} ms maxsize={m:2d}: avg latency {avg:7.2f} ms, "
            f"max {mx:7.2f} ms, producer blocked in {blk:4.1f}/20 puts (mean of 3 runs)")

fig, ax = plt.subplots(figsize=(7, 3.8))
ax.plot(sizes, [sweep[(0.006, m)][0] for m in sizes], "o-", label="slow consumer (6 ms per item), average")
ax.plot(sizes, [sweep[(0.006, m)][1] for m in sizes], "s--", label="slow consumer, maximum")
ax.plot(sizes, [sweep[(0.0, m)][0] for m in sizes], "^-", label="fast consumer, average")
ax.set_xlabel("queue maxsize")
ax.set_ylabel("send-to-receipt latency (ms)")
ax.set_xticks(sizes)
ax.grid(alpha=0.35)
ax.legend(fontsize=8)
ax.set_title("Message-queue latency versus queue depth (20 items, mean of 3 runs)", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_queue_latency_vs_maxsize.png"), dpi=160)
plt.close(fig)

# ------------------------------------------------------------------ semaphore pool
say("=" * 78)
say("Steps 7-8 and lab task 2: counting semaphore, 8 tasks, same hold times for every count")
sem = {}
for count in (1, 3, 6):
    waits, mx, holds = semaphore_pool.run(count, 8, seed=1)
    sem[count] = (waits, mx)
    nz = sum(w > 0.001 for w in waits)
    say(f"  Semaphore({count}): max holders {mx}, tasks that waited {nz}/8, mean wait "
        f"{1000 * statistics.mean(waits):6.1f} ms, max wait {1000 * max(waits):6.1f} ms, "
        f"per-task waits ms {[round(1000 * w, 1) for w in waits]}")
say(f"  hold times ms {[round(1000 * h, 1) for h in holds]}")
fig, ax = plt.subplots(figsize=(7.5, 3.6))
w = 0.27
for k, count in enumerate((1, 3, 6)):
    ax.bar([i + (k - 1) * w for i in range(8)], [1000 * x for x in sem[count][0]], w,
           label=f"Semaphore({count}), max holders {sem[count][1]}")
ax.set_xlabel("task")
ax.set_ylabel("wait before acquiring (ms)")
ax.set_xticks(range(8))
ax.grid(axis="y", alpha=0.35)
ax.legend(fontsize=8)
ax.set_title("Wait time per task for three semaphore counts", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_semaphore_waits.png"), dpi=160)
plt.close(fig)

# ------------------------------------------------------------------ dispatch latency
say("=" * 78)
say("Step 9: dispatch latency, 3 runs of 200 iterations")
all_us = []
for r in range(3):
    us = [1e6 * x for x in timing_overhead.measure(200)]
    all_us += us
    say(f"  run {r + 1}: min {min(us):6.1f}  mean {statistics.mean(us):6.1f}  median {statistics.median(us):6.1f}  "
        f"p95 {timing_overhead.p95(us):6.1f}  max (worst-case observed) {max(us):7.1f} us")
fig, ax = plt.subplots(figsize=(7, 3.6))
ax.hist(all_us, bins=60, color="#1f77b4")
for v, lab, c in ((statistics.mean(all_us), "mean", "black"), (timing_overhead.p95(all_us), "p95", "#ff7f0e"),
                  (max(all_us), "max", "#d62728")):
    ax.axvline(v, color=c, ls="--", lw=1)
    ax.text(v, ax.get_ylim()[1] * 0.9, f" {lab} {v:.0f} us", color=c, fontsize=8)
ax.set_xlabel("start-thread-to-event-wake interval (microseconds)")
ax.set_ylabel("count (600 samples)")
ax.set_title("Dispatch latency distribution: small average, long tail", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_dispatch_latency.png"), dpi=160)
plt.close(fig)

# ------------------------------------------------------------------ livelock
say("=" * 78)
say("Lab task 3: livelock")
r, c, dt = livelock_demo.run(2000, 50, randomized=False)
say(f"  lock-step back-off: 2000 rounds in {dt:.2f}s, retries T1={r['T1']} T2={r['T2']}, "
    f"work done T1={c['T1']}/50 T2={c['T2']}/50 -> livelock")
r, c, dt = livelock_demo.run(2000, 50, randomized=True)
say(f"  random back-off  : {dt:.2f}s, retries T1={r['T1']} T2={r['T2']}, work done T1={c['T1']}/50 T2={c['T2']}/50")

with open(os.path.join(HERE, "results_3_1.txt"), "w") as f:
    f.write("\n".join(LOG) + "\n")
print("results written to results_3_1.txt, figures to", FIG)
