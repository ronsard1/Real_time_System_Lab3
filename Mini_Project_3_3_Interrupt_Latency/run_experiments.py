"""
run_experiments.py - Mini Project 3.3 driver.

Configurations (periods are deliberately non-harmonic so every phase relation occurs):
  A baseline      : short top halves everywhere (Section 3.5 guidance)
  B long TH (low) : the LOW-priority logger does all of its work in its top half (6 ms, masked)
  C long TH (high): the HIGH-priority sensor does all of its work in its top half (2 ms, masked)
B and C keep each source's total work (TH + BH) the same as in A, so any change is caused only
by moving work from the bottom half into the top half.

Sweep: highest-priority source period 20 -> 3 ms (baseline durations), lowest-priority worst case.

    python Mini_Project_3_3_Interrupt_Latency/run_experiments.py [--duration 20] [--sweep-duration 10]
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from irq_sim import Source, run, stats, rta_bound, SLICE_MS, host_stalls  # noqa: E402

FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)
LOG = []


def say(s=""):
    print(s, flush=True)
    LOG.append(s)


def baseline(p1=10.0):
    return [Source("S1_sensor", p1, 0.2, 2.0, 3),
            Source("S2_network", 23.0, 0.2, 3.0, 2, offset_ms=1.3),
            Source("S3_logger", 47.0, 0.2, 6.0, 1, offset_ms=2.9)]


CONFIGS = {
    "A baseline (short top halves)": baseline(),
    "B long top half on LOW-priority S3": [Source("S1_sensor", 10.0, 0.2, 2.0, 3),
                                           Source("S2_network", 23.0, 0.2, 3.0, 2, offset_ms=1.3),
                                           Source("S3_logger", 47.0, 6.0, 0.2, 1, offset_ms=2.9)],
    "C long top half on HIGH-priority S1": [Source("S1_sensor", 10.0, 2.0, 0.2, 3),
                                            Source("S2_network", 23.0, 0.2, 3.0, 2, offset_ms=1.3),
                                            Source("S3_logger", 47.0, 0.2, 6.0, 1, offset_ms=2.9)],
}


def plot_comparison(rows, path):
    """rows: dicts from results_3_3_configs.csv. Bars = 95th percentile (robust against host noise),
    open markers = stall-filtered maximum, dots = mean."""
    names = ["S1_sensor", "S2_network", "S3_logger"]
    cfgs = list(dict.fromkeys(r["config"] for r in rows))
    get = {(r["config"], r["source"]): r for r in rows}
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    for ax, key, title in ((axes[0], "irq", "Interrupt latency"), (axes[1], "resp", "Response latency")):
        for k, cname in enumerate(cfgs):
            xs = [i + (k - 1) * 0.27 for i in range(3)]
            ax.bar(xs, [float(get[(cname, n)][f"{key}_p95"]) for n in names], 0.27, label=cname,
                   color=["#1f77b4", "#d62728", "#ff7f0e"][k], alpha=0.85)
            ax.scatter(xs, [float(get[(cname, n)][f"{key}_max_clean"]) for n in names], facecolors="none",
                       edgecolors="black", s=22, zorder=3, label="max* (includes host noise)" if k == 0 else None)
            ax.scatter(xs, [float(get[(cname, n)][f"{key}_mean"]) for n in names], color="black", s=10, zorder=3,
                       label="mean" if k == 0 else None)
        ax.set_xticks(range(3))
        ax.set_xticklabels(names)
        ax.set_ylabel("ms")
        ax.set_title(f"{title}: 95th percentile (bars), max* (circle), mean (dot)", fontsize=9.5)
        ax.grid(axis="y", alpha=0.35)
    axes[0].legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_sweep(sweep, path):
    """sweep rows: (S1 period, load, S3 mean, S3 p95, S3 max*, bound, S1 max*, S3 raw max)."""
    fig, ax = plt.subplots(figsize=(7.5, 4))
    xs = [r[0] for r in sweep]
    ax.plot(xs, [r[5] for r in sweep], "k--", lw=1.5, label="S3 analytic bound (RTA)")
    ax.plot(xs, [r[3] for r in sweep], "s-", color="#ff7f0e", label="S3 measured p95")
    ax.plot(xs, [r[2] for r in sweep], "^-", color="#2ca02c", label="S3 measured mean")
    ax.plot(xs, [r[4] for r in sweep], "o", mfc="none", color="#d62728", label="S3 measured max* (host noise included)")
    for r in sweep:
        ax.annotate(f"{100 * r[1]:.0f}%", (r[0], r[2]), textcoords="offset points", xytext=(-6, -14), fontsize=7)
    ax.invert_xaxis()
    ax.set_ylim(0, 80)
    ax.set_xlabel("S1 (highest priority) period, ms  ->  higher arrival rate (labels = CPU load)")
    ax.set_ylabel("S3 response latency (ms)")
    ax.grid(alpha=0.35)
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title("Lowest-priority response latency as high-priority arrival rate grows", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--sweep-duration", type=float, default=10.0)
    a = ap.parse_args()

    say(f"bottom-half slice (preemption granularity) = {SLICE_MS} ms; durations: configs {a.duration} s, "
        f"sweep points {a.sweep_duration} s")
    say("max* = maximum after excluding occurrences that overlap a host stall (the OS descheduling the simulator)")
    rows = []
    results = {}
    for cname, srcs in CONFIGS.items():
        load = sum((s.th_ms + s.bh_ms) / s.period_ms for s in srcs)
        say("=" * 96)
        say(f"{cname}: CPU load {100 * load:.1f}%")
        for s in srcs:
            say(f"   {s.name:11s} period {s.period_ms:5.1f} ms  TH {s.th_ms:4.1f} ms  BH {s.bh_ms:4.1f} ms  "
                f"priority {s.priority}  analytic worst response {rta_bound(srcs, s):6.2f} ms")
        res = run(srcs, a.duration, record_segments_s=a.duration)
        results[cname] = res
        st = stats(res)
        pd = sorted(res.host_post_delay_us)
        say(f"   host wake-up jitter of the source threads: median {pd[len(pd) // 2]:.0f} us, "
            f"max {pd[-1]:.0f} us")
        hs = host_stalls(res)
        say(f"   host stalls detected (work unit > 0.5 ms longer than requested): {len(hs)}, longest "
            f"{max([1000 * (b - a) for a, b in hs], default=0):.1f} ms")
        say(f"   {'source':11s}{'n':>5s} | {'IRQ lat mean':>12s}{'p95':>8s}{'max':>8s}{'max*':>7s} | {'TH':>5s} | "
            f"{'resp min':>9s}{'mean':>7s}{'p95':>7s}{'max':>7s}{'max*':>7s} | {'bound':>6s} | preempted | stall-hit")
        for s in srcs:
            v = st[s.name]
            say(f"   {s.name:11s}{v['n']:>5d} | {v['irq_mean']:>12.3f}{v['irq_p95']:>8.3f}{v['irq_max']:>8.3f}"
                f"{v['irq_max_clean']:>7.2f} | {v['th_mean']:>5.2f} | {v['resp_min']:>9.2f}{v['resp_mean']:>7.2f}"
                f"{v['resp_p95']:>7.2f}{v['resp_max']:>7.2f}{v['resp_max_clean']:>7.2f} | {rta_bound(srcs, s):>6.2f} | "
                f"{v['preempted']:>4d}/{v['n']:<4d} | {v['affected_by_stall']}")
            rows.append({"config": cname, "source": s.name, **{k: round(x, 4) if isinstance(x, float) else x
                                                               for k, x in v.items()},
                         "rta_bound_ms": round(rta_bound(srcs, s), 3)})
        # per-occurrence log
        tag = cname.split()[0]
        with open(os.path.join(HERE, f"log_config_{tag}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["source", "k", "assert_ms", "irq_latency_ms", "top_half_ms", "response_ms", "bh_preempted"])
            t0 = min(o.t_assert for o in res.occ)
            for o in sorted(res.occ, key=lambda o: o.t_assert):
                w.writerow([o.src, o.k, round(1000 * (o.t_assert - t0), 3), round(1000 * (o.t_th_start - o.t_assert), 4),
                            round(1000 * (o.t_th_end - o.t_th_start), 4), round(1000 * (o.t_bh_done - o.t_assert), 4),
                            o.bh_preempted])
    with open(os.path.join(HERE, "results_3_3_configs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---------------------------------------------------------- comparison chart
    plot_comparison(rows, os.path.join(FIG, "fig_config_comparison.png"))

    # ---------------------------------------------------------- timelines
    def timeline(res, center_ms, path, title, span=24.0):
        lo, hi = center_ms - span / 2, center_ms + span / 2
        fig, ax = plt.subplots(figsize=(11, 2.9))
        col = {"S1_sensor": "#1f77b4", "S2_network": "#2ca02c", "S3_logger": "#9467bd"}
        y = {"S1_sensor": 2, "S2_network": 1, "S3_logger": 0}
        for (a0, a1, src, kind) in res.segments:
            ms0, ms1 = 1000 * a0, 1000 * a1
            if ms1 < lo or ms0 > hi:
                continue
            ax.broken_barh([(ms0, ms1 - ms0)], (y[src] - 0.35, 0.7),
                           facecolors=col[src] if kind == "BH" else "#d62728",
                           edgecolor="black", linewidth=0.3, hatch="" if kind == "BH" else "////")
        for o in res.occ:
            ms = 1000 * (o.t_assert - res.t0_abs)
            if lo <= ms <= hi:
                ax.plot(ms, y[o.src] + 0.45, marker="v", color="black", ms=6)
        ax.set_yticks([0, 1, 2])
        ax.set_yticklabels(["S3_logger (prio 1)", "S2_network (prio 2)", "S1_sensor (prio 3)"])
        ax.set_xlim(lo, hi)
        ax.set_xlabel("time (ms)")
        ax.grid(axis="x", alpha=0.3)
        ax.set_title(title, fontsize=10)
        ax.legend(handles=[Patch(facecolor="#d62728", hatch="////", label="top half (interrupts masked)"),
                           Patch(color="#1f77b4", label="S1 bottom half"), Patch(color="#2ca02c", label="S2 bottom half"),
                           Patch(color="#9467bd", label="S3 bottom half"),
                           plt.Line2D([], [], marker="v", ls="", color="black", label="interrupt asserted")],
                  fontsize=7, loc="upper right", ncol=5)
        ax.set_ylim(-0.6, 3.1)
        fig.tight_layout()
        fig.savefig(path, dpi=160)
        plt.close(fig)

    for cname, tag, src in (("B long top half on LOW-priority S3", "B", "S1_sensor"),
                            ("A baseline (short top halves)", "A", "S3_logger")):
        res = results[cname]
        stalls = host_stalls(res)

        def clean(o):                                   # occurrence not touched by a host stall
            a, b = o.t_assert - res.t0_abs, o.t_bh_done - res.t0_abs
            return not any(s0 < b + 0.002 and s1 > a - 0.002 for s0, s1 in stalls)
        if tag == "B":
            worst = max((o for o in res.occ if o.src == src and clean(o)), key=lambda o: o.t_th_start - o.t_assert)
            title = (f"Config B: S1 asserted during S3's 6 ms masked top half; S1 interrupt latency "
                     f"{1000 * (worst.t_th_start - worst.t_assert):.2f} ms")
        else:
            cand = sorted((o for o in res.occ if o.src == src and o.bh_preempted >= 2 and clean(o)),
                          key=lambda o: o.t_bh_done - o.t_assert)
            worst = cand[int(0.9 * (len(cand) - 1))]            # a typical long case, not a host-stall outlier
            title = (f"Config A: S3 bottom half preempted {worst.bh_preempted} times; response "
                     f"{1000 * (worst.t_bh_done - worst.t_assert):.2f} ms")
        center = 1000 * (worst.t_assert - res.t0_abs) + 8
        timeline(res, center, os.path.join(FIG, f"fig_timeline_config_{tag}.png"), title,
                 span=26.0 if tag == "B" else 30.0)

    # ---------------------------------------------------------- arrival-rate sweep
    say("=" * 96)
    say("Sweep: S1 period (arrival rate) vs S3 (lowest priority) response latency, baseline durations")
    sweep = []
    for p1 in (20.0, 10.0, 6.0, 4.0, 3.5, 3.2):
        srcs = baseline(p1)
        load = sum((s.th_ms + s.bh_ms) / s.period_ms for s in srcs)
        res = run(srcs, a.sweep_duration, record_segments_s=a.sweep_duration)
        st = stats(res)
        v = st["S3_logger"]
        bnd = rta_bound(srcs, srcs[2])
        sweep.append((p1, load, v["resp_mean"], v["resp_p95"], v["resp_max_clean"], bnd, st["S1_sensor"]["resp_max_clean"],
                      v["resp_max"]))
        say(f"   S1 period {p1:4.1f} ms (load {100 * load:5.1f}%): S3 response mean {v['resp_mean']:8.2f}  "
            f"p95 {v['resp_p95']:8.2f}  max* {v['resp_max_clean']:8.2f}  (raw max {v['resp_max']:8.2f}) ms; "
            f"analytic bound {bnd:7.2f} ms; S1 max* {st['S1_sensor']['resp_max_clean']:.2f} ms")
    with open(os.path.join(HERE, "results_3_3_sweep.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["S1_period_ms", "cpu_load", "S3_resp_mean_ms", "S3_resp_p95_ms", "S3_resp_max_clean_ms",
                    "S3_rta_bound_ms", "S1_resp_max_clean_ms", "S3_resp_max_raw_ms"])
        for r in sweep:
            w.writerow([round(x, 4) for x in r])
    plot_sweep(sweep, os.path.join(FIG, "fig_sweep_s1_period.png"))

    with open(os.path.join(HERE, "results_3_3.txt"), "w") as f:
        f.write("\n".join(LOG) + "\n")
    print("results written; figures in", FIG)


if __name__ == "__main__":
    main()
