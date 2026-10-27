# Real-Time Systems – Lab 3 (Unit 3 Mini Projects)

University of Rwanda, College of Science and Technology, School of ICT, Department of Computer Engineering
Group 3: Ronsard RUGIRANGOGA (223026673), Ivan MULISA (223026695), Dieudonne BYIRINGIRO (223026513)

Python `threading` used as a sandbox for RTOS concurrency: each thread is an RTOS task,
`threading.Lock` a mutex, `threading.Semaphore` a counting semaphore, a bounded `queue.Queue` a
message queue. The written report summarises the results; this repository holds the complete
source, the raw console output of every run, the per-occurrence latency logs and all charts.

## Structure

```
Mini_Project_3_1_Concurrency/
    race_demo.py, race_fixed.py      lost-update race and its mutex fix (--threads, --runs)
    queue_sim.py                     bounded message queue, send-to-receipt latency
    semaphore_pool.py                counting semaphore guarding a resource pool
    timing_overhead.py               dispatch-latency measurement (200 iterations)
    livelock_demo.py                 lab task 3: two locks, opposite order, polite back-off
    run_all.py                       runs everything incl. lab tasks -> results_3_1.txt, figures/
Mini_Project_3_2_Deadlock_Buffer/
    bounded_buffer.py                3P/3C bounded buffer, buffer_lock + stats_lock, watchdog,
                                     Config(lock_order="flawed" | "fixed", capacity, ...)
    run_experiments.py               deadlock reproduction, fix, capacity sweep
    results_3_2.txt, results_3_2_capacity.csv, figures/
Mini_Project_3_3_Interrupt_Latency/
    irq_sim.py                       top-half / bottom-half simulator, priority heapq, preemptible
                                     bottom halves, host-stall detection, RTA bound
    run_experiments.py               configurations A/B/C, arrival-rate sweep, timelines
    overload_check.py                one extra point beyond 100 % CPU load
    log_config_A.csv, log_config_B.csv, log_config_C.csv   per-occurrence latency logs
    results_3_3.txt, results_3_3_configs.csv, results_3_3_sweep.csv, results_3_3_overload.txt, figures/
```

## Run

Python 3.9 or later; the simulations use the standard library (threading, time, queue, heapq); NumPy and Matplotlib are used for the statistics and charts.

```
pip install -r requirements.txt
python Mini_Project_3_1_Concurrency/run_all.py                    (~15 s)
python Mini_Project_3_2_Deadlock_Buffer/run_experiments.py        (~2 min)
python Mini_Project_3_3_Interrupt_Latency/run_experiments.py      (~2.5 min; --duration / --sweep-duration shorten it)
python Mini_Project_3_3_Interrupt_Latency/overload_check.py       (~10 s)
```

These programs measure real time on real threads, so exact numbers change slightly between runs
and machines; the qualitative results (lost updates, the deadlock and its fix, the long-top-half
effects) reproduce every time. Results in the report were measured on a 2-vCPU cloud Linux VM with
Python 3.13.
