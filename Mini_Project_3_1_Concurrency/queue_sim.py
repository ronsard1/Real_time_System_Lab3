"""
queue_sim.py - bounded message queue between a producer task and a consumer task (steps 5-6).

queue.Queue(maxsize=5) behaves like an RTOS message queue: put() blocks the producer when the
queue is full, get() blocks the consumer when it is empty. Each item carries its send
timestamp, and the consumer records send-to-receipt latency.

    python queue_sim.py [--maxsize 5] [--items 20] [--consumer-delay 0.0] [--producer-delay 0.002]
"""
import argparse
import queue
import statistics
import threading
import time


def run(maxsize=5, items=20, consumer_delay=0.0, producer_delay=0.002):
    q = queue.Queue(maxsize=maxsize)
    latencies = []
    put_blocked = []            # time the producer spent blocked inside put()

    def producer_task():
        for i in range(items):
            time.sleep(producer_delay)          # producer's own work between messages
            sent = time.perf_counter()
            q.put((i, sent))                    # blocks while the queue is full
            put_blocked.append(time.perf_counter() - sent)
        q.put(None)                             # end-of-stream marker

    def consumer_task():
        while True:
            msg = q.get()                       # blocks while the queue is empty
            if msg is None:
                break
            _, sent = msg
            latencies.append(time.perf_counter() - sent)
            if consumer_delay:
                time.sleep(consumer_delay)      # slow consumer: simulated processing time

    p = threading.Thread(target=producer_task)
    c = threading.Thread(target=consumer_task)
    c.start()
    p.start()
    p.join()
    c.join()
    blocked = [b for b in put_blocked if b > 0.0005]       # put() calls that really waited
    return {
        "maxsize": maxsize, "consumer_delay_ms": 1000 * consumer_delay,
        "lat_min_ms": 1000 * min(latencies), "lat_max_ms": 1000 * max(latencies),
        "lat_avg_ms": 1000 * statistics.mean(latencies),
        "blocked_puts": len(blocked), "blocked_total_ms": 1000 * sum(blocked),
    }


def fmt(r):
    return (f"maxsize={r['maxsize']:>2} consumer_delay={r['consumer_delay_ms']:4.1f} ms | latency min "
            f"{r['lat_min_ms']:7.3f}  avg {r['lat_avg_ms']:7.3f}  max {r['lat_max_ms']:7.3f} ms | "
            f"producer blocked in {r['blocked_puts']:2d}/20 puts, {r['blocked_total_ms']:6.1f} ms total")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maxsize", type=int, default=5)
    ap.add_argument("--items", type=int, default=20)
    ap.add_argument("--consumer-delay", type=float, default=0.0)
    ap.add_argument("--producer-delay", type=float, default=0.002)
    a = ap.parse_args()
    print(fmt(run(a.maxsize, a.items, a.consumer_delay, a.producer_delay)))


if __name__ == "__main__":
    main()
