"""
overload_check.py - one extra sweep point beyond 100 % CPU load (S1 period 2.6 ms), run on its own
so it cannot disturb the main experiments. Shows that the lowest-priority response time no longer
converges once the load exceeds 1: it grows for as long as the run lasts.

    python Mini_Project_3_3_Interrupt_Latency/overload_check.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from irq_sim import run, stats  # noqa: E402
from run_experiments import baseline  # noqa: E402

srcs = baseline(2.6)
load = sum((s.th_ms + s.bh_ms) / s.period_ms for s in srcs)
res = run(srcs, 10.0, record_segments_s=10.0)
v = stats(res)["S3_logger"]
oc = sorted((o for o in res.occ if o.src == "S3_logger"), key=lambda o: o.t_assert)
first = [round(1000 * (o.t_bh_done - o.t_assert), 1) for o in oc[:3]]
t0 = oc[0].t_assert
quarters = []
for qi in range(4):
    rs = [1000 * (o.t_bh_done - o.t_assert) for o in oc if qi * 2.5 <= o.t_assert - t0 < (qi + 1) * 2.5]
    quarters.append(round(sum(rs) / len(rs)) if rs else None)
n1 = sum(1 for o in res.occ if o.src == "S1_sensor")
eff = sum((s.th_ms + s.bh_ms) * sum(1 for o in res.occ if o.src == s.name) for s in srcs) / 10000.0
txt = (f"S1 period 2.6 ms, nominal CPU load {100 * load:.1f}% (completed work {100 * eff:.1f}% of 10 s, "
       f"S1 completed {n1} jobs): S3 completed {v['n']} jobs; response mean "
       f"{v['resp_mean']:.0f} ms, p95 {v['resp_p95']:.0f} ms, max {v['resp_max']:.0f} ms; "
       f"first three responses {first} ms; mean response of S3 jobs asserted in each 2.5 s quarter of the run "
       f"{quarters} ms (the backlog keeps growing while the overload lasts)")
print(txt)
with open(os.path.join(HERE, "results_3_3_overload.txt"), "w") as f:
    f.write(txt + "\n")
