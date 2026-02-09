import cProfile
import pstats
import main
from collections import defaultdict
import os
import time
from io import StringIO
from core.simulation import Simulation, SIM_QUIT

THRESHOLD = 1000 #minimum no of function calls so that it is printed
RESULTS_FILE = "benchmark_results.txt"
BENCH_DURATION_SECONDS = 10

_bench_start = None
_orig_handle_events = Simulation.handle_events

def _handle_events_with_limit(self):
    global _bench_start
    if _bench_start is None:
        _bench_start = time.perf_counter()
    if time.perf_counter() - _bench_start >= BENCH_DURATION_SECONDS:
        return SIM_QUIT
    return _orig_handle_events(self)

Simulation.handle_events = _handle_events_with_limit

def run():
    main.main()
    
profiler = cProfile.Profile()
start_time = time.perf_counter()
profiler.enable()

try:
    run()
except SystemExit:
    pass
finally:
    profiler.disable()
    end_time = time.perf_counter()

stats = pstats.Stats(profiler)
stats.sort_stats("calls")

call_counts = defaultdict(int)

for func, data in stats.stats.items():
    filename, lineno, funcname = func
    total_calls = data[1]   

    module = os.path.splitext(os.path.basename(filename))[0]
    key = f"{module}.{funcname}"

    call_counts[key] += total_calls

for name, count in sorted(call_counts.items(), key=lambda x: x[1], reverse=True):
    if count > THRESHOLD:
        print(f"{name:40s} {count}")

print("No of function calls:", sum(call_counts.values()), f" in {end_time-start_time:.5f}")

def _format_stats(profile):
    output = StringIO()
    output.write("--- top cumulative ---\n")
    pstats.Stats(profile, stream=output).sort_stats("cumulative").print_stats(30)
    output.write("\n--- top tottime ---\n")
    pstats.Stats(profile, stream=output).sort_stats("tottime").print_stats(30)
    return output.getvalue()

def _format_call_counts(counts):
    lines = ["--- top calls (threshold > {threshold}) ---".format(threshold=THRESHOLD)]
    for name, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        if count > THRESHOLD:
            lines.append(f"{name:40s} {count}")
    lines.append("No of function calls: {total} in {duration:.5f}".format(
        total=sum(counts.values()),
        duration=end_time - start_time
    ))
    return "\n".join(lines)

def _write_results():
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    header = f"\n=== Benchmark Run @ {timestamp} (limit={BENCH_DURATION_SECONDS}s) ===\n"
    data = _format_call_counts(call_counts) + "\n\n" + _format_stats(profiler)
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(header)
        f.write(data)
        f.write("\n")

_write_results()