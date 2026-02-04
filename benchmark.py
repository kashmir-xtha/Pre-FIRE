import cProfile
import pstats
import main
from collections import defaultdict
import os
import time 

THRESHOLD = 1000 #minimum no of function calls so that it is printed

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