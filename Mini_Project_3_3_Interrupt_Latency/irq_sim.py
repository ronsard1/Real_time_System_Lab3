"""
irq_sim.py - priority-based interrupt latency simulator (Mini Project 3.3).

Model (Section 3.5)
  * Each interrupt SOURCE is a thread that sleeps for its period and then asserts its interrupt
    line: it records an assertion timestamp (time.perf_counter) and posts the request.
  * One simulated CPU (the main thread) runs everything else:
      - TOP HALVES always run first. A top half runs to completion with interrupts masked
        (it cannot be interrupted, as on most MCUs), then queues its BOTTOM HALF into a
        priority queue (heapq) tagged with priority and assertion time.
      - BOTTOM HALVES run by strict priority, in slices of SLICE_MS. Between slices the CPU checks
        for newly asserted interrupts and for a higher-priority bottom half, so a bottom half can be
        preempted mid-execution; its remaining work is re-queued.
  * Work is simulated by busy-waiting on time.perf_counter(), so durations are real CPU time.

Per occurrence it logs: interrupt latency (assertion -> first top-half instruction), top-half
duration, and response latency (assertion -> bottom half completed).

Limitations (stated in the report): Python cannot deliver a real interrupt, so a top half can start
only at a slice boundary (preemption granularity = SLICE_MS) and the host OS adds jitter to every
wake-up. The GIL switch interval is lowered to 100 us so source threads can post promptly.
"""
from __future__ import annotations

import heapq

import numpy as np
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field

SLICE_MS = 0.25           # bottom-half preemption granularity


@dataclass
class Source:
    name: str
    period_ms: float
    th_ms: float              # top-half duration
    bh_ms: float              # bottom-half duration
    priority: int             # larger = more urgent (both for top halves and bottom halves)
    offset_ms: float = 0.0


@dataclass
class Occurrence:
    src: str
    k: int
    t_assert: float
    t_th_start: float = 0.0
    t_th_end: float = 0.0
    t_bh_done: float = 0.0
    bh_preempted: int = 0     # how many times this bottom half was interrupted mid-execution


@dataclass
class RunResult:
    sources: list
    occ: list
    segments: list = field(default_factory=list)   # (t0, t1, src, kind) kind in {"TH","BH"}
    duration_s: float = 0.0
    host_post_delay_us: list = field(default_factory=list)
    t0_abs: float = 0.0                              # simulator time origin (segments are relative to it)


def busy(ms):
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        pass


def run(sources: list[Source], duration_s=20.0, record_segments_s=1.0) -> RunResult:
    old_si = sys.getswitchinterval()
    sys.setswitchinterval(1e-4)
    pending: list = []                         # posted top-half requests: (−prio, t_assert, seq, Occurrence)
    pend_lock = threading.Lock()
    occ_all: list[Occurrence] = []
    stop = threading.Event()
    post_delay = []
    seq = [0]
    t0 = time.perf_counter() + 0.05            # common start

    def source_thread(s: Source):
        k = 0
        last = -1e9
        while not stop.is_set():
            # strictly periodic schedule, but never two assertions closer than one period: if the host
            # woke this thread late, the next assertion is pushed back instead of firing a catch-up burst
            due = max(t0 + (s.offset_ms + k * s.period_ms) / 1000.0, last + s.period_ms / 1000.0)
            now = time.perf_counter()
            if due > now:
                time.sleep(due - now)                          # sleep until the next period (no spinning:
                                                               # a spinning source would steal simulated CPU time)
            t_assert = time.perf_counter()                     # interrupt line asserted
            post_delay.append(1e6 * (t_assert - due))
            last = t_assert
            o = Occurrence(s.name, k, t_assert)
            with pend_lock:
                seq[0] += 1
                heapq.heappush(pending, (-s.priority, t_assert, seq[0], o))
                occ_all.append(o)
            k += 1
            if t_assert - t0 > duration_s:
                return

    by_name = {s.name: s for s in sources}
    threads = [threading.Thread(target=source_thread, args=(s,), daemon=True) for s in sources]
    for th in threads:
        th.start()

    bh_heap: list = []                         # (−prio, t_assert, seq, Occurrence, remaining_ms)
    segments = []
    last_bh = None                             # occurrence whose slice ran most recently
    bseq = 0
    rec_until = t0 + record_segments_s
    while True:
        now = time.perf_counter()
        if now - t0 > duration_s and not bh_heap and not pending:
            break
        # 1) top halves first, highest priority pending interrupt
        req = None
        with pend_lock:
            if pending:
                req = heapq.heappop(pending)
        if req is not None:
            _, _, _, o = req
            s = by_name[o.src]
            if last_bh is not None and last_bh.t_bh_done == 0.0:
                last_bh.bh_preempted += 1                       # a bottom half was cut off by this top half
                last_bh = None
            o.t_th_start = time.perf_counter()
            busy(s.th_ms)                                       # top half (interrupts masked)
            o.t_th_end = time.perf_counter()
            if o.t_th_start < rec_until:
                segments.append((o.t_th_start - t0, o.t_th_end - t0, o.src, "TH"))
            bseq += 1
            heapq.heappush(bh_heap, (-s.priority, o.t_assert, bseq, o, s.bh_ms))
            continue
        # 2) highest-priority bottom half, one slice
        if bh_heap:
            negp, ta, sq, o, rem = heapq.heappop(bh_heap)
            if last_bh is not None and last_bh is not o and last_bh.t_bh_done == 0.0:
                last_bh.bh_preempted += 1                       # preempted by a higher-priority bottom half
            sl = min(SLICE_MS, rem)
            a = time.perf_counter()
            busy(sl)
            b = time.perf_counter()
            if a < rec_until:
                segments.append((a - t0, b - t0, o.src, "BH"))
            rem -= sl
            if rem > 1e-9:
                heapq.heappush(bh_heap, (negp, ta, sq, o, rem))   # re-queue the remainder
            else:
                o.t_bh_done = b
            last_bh = o
            continue
        # 3) idle: give the source threads the interpreter
        time.sleep(0)
    stop.set()
    sys.setswitchinterval(old_si)
    done = [o for o in occ_all if o.t_bh_done > 0]
    return RunResult(sources, done, segments, duration_s, post_delay, t0)


def p95(xs):
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]


def host_stalls(res: RunResult, tol_ms=0.5):
    """Intervals (relative to t0, seconds) where a simulated work unit took more than tol_ms longer than
    requested: the host OS descheduled the whole simulator (a VM or OS effect, not part of the model)."""
    th = {s.name: s.th_ms for s in res.sources}
    out = []
    for (a0, a1, src, kind) in res.segments:
        nominal = th[src] if kind == "TH" else SLICE_MS
        if 1000 * (a1 - a0) > nominal + tol_ms:
            out.append((a0, a1))
    return out


def stats(res: RunResult):
    """Per-source statistics in milliseconds. *_clean maxima exclude occurrences whose
    assertion-to-completion window overlaps a host stall."""
    out = {}
    stalls = host_stalls(res)
    st_arr = np.array(stalls) if stalls else np.zeros((0, 2))
    for s in res.sources:
        oc = [o for o in res.occ if o.src == s.name]
        hit = []
        for o in oc:
            a, b = o.t_assert - res.t0_abs, o.t_bh_done - res.t0_abs
            hit.append(bool(len(st_arr)) and bool(np.any((st_arr[:, 0] < b) & (st_arr[:, 1] > a))))
        il = [1000 * (o.t_th_start - o.t_assert) for o in oc]
        rl = [1000 * (o.t_bh_done - o.t_assert) for o in oc]
        th = [1000 * (o.t_th_end - o.t_th_start) for o in oc]
        out[s.name] = {
            "n": len(oc),
            "irq_min": min(il), "irq_mean": statistics.mean(il), "irq_max": max(il), "irq_p95": p95(il),
            "th_mean": statistics.mean(th),
            "resp_min": min(rl), "resp_mean": statistics.mean(rl), "resp_max": max(rl), "resp_p95": p95(rl),
            "preempted": sum(o.bh_preempted > 0 for o in oc),
            "affected_by_stall": sum(hit),
            "irq_max_clean": max(x for x, h in zip(il, hit) if not h),
            "resp_max_clean": max(x for x, h in zip(rl, hit) if not h),
        }
    return out


def rta_bound(sources: list[Source], target: Source, slice_ms=SLICE_MS):
    """Response-time bound for `target` (assertion -> bottom half done), Section 2.5.2 style, in ms:
        R = B + TH_t + BH_t + sum_{all j != t} ceil(R/T_j)*TH_j + sum_{higher-priority j} ceil(R/T_j)*BH_j
    Every top half, even one of a LOWER-priority source, preempts our bottom half, so all top halves are
    interference. A lower-priority top half already running when we assert is covered by the same term
    (the analysis window starts when it started). B = one non-preemptible bottom-half slice."""
    import math
    if sum((s.th_ms + s.bh_ms) / s.period_ms for s in sources) > 1.0:
        return float("inf")                     # overloaded CPU: no finite bound exists
    B = slice_ms
    R = target.th_ms + target.bh_ms + B
    for _ in range(1000):
        new = B + target.th_ms + target.bh_ms
        for s in sources:
            if s is target:
                continue
            n = math.ceil(R / s.period_ms)
            new += n * s.th_ms
            if s.priority > target.priority:
                new += n * s.bh_ms
        if abs(new - R) < 1e-9:
            return R
        if new > 10_000:
            return float("inf")
        R = new
    return float("inf")
