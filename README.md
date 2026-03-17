# Pre-FIRE — Fire Evacuation Simulation

A physics-based building evacuation simulator with real-time fire and smoke propagation, multi-agent pathfinding, and statistical analysis tools.

---

## Overview

Pre-FIRE simulates occupant evacuation under fire conditions in configurable building layouts. It models fire spread, smoke diffusion, and heat transfer using physically grounded equations, and drives agents with A\* pathfinding that dynamically replans as hazards evolve. A headless Monte Carlo engine sits alongside the interactive simulator for batch statistical analysis.

---

## Screenshots

### Layout Editor
<img alt="Layout Editor" src="https://github.com/user-attachments/assets/075011d4-04d4-459b-be87-c69133cadf5c" />

### Simulation
<img alt="Simulation" src="https://github.com/user-attachments/assets/8537d0a8-e344-4b85-899a-43ce11fcfaa2" />


---

## Features

- Real-time fire, smoke, and temperature physics per material type
- A\* pathfinding with dynamic replanning, fire avoidance, and stress modelling
- Up to 3 agents per floor with distinct vulnerability profiles
- Multi-floor buildings with stairwell traversal
- Built-in layout editor with CSV import/export
- FED (Fractional Effective Dose) incapacitation model for smoke and heat
- Side panel with live metrics (health bars, evac time, fire cells, smoke density)
- Snapshot and CSV export for post-run analysis
- Headless Monte Carlo survival heatmap
- Headless Monte Carlo congestion / bottleneck map

---

## Requirements

- Python 3.11+

Install dependencies:

```bash
pip install -r requirements.txt
```

**`requirements.txt`**
```
pygame-ce>=2.5.6
pygame-gui>=0.6.14
numpy>=1.26.4
matplotlib>=3.10.0
tqdm>=4.67.3
Pillow>=10.4.0
pytest>=9.0.2
```

---

## Project Structure

```
Pre-FIRE/
├── main.py                        # Entry point
├── core/
│   ├── agent/
│   │   ├── agent.py               # Agent class (composition root)
│   │   ├── agent_movement.py      # FED damage, speed, stress, stairwell traversal
│   │   ├── agent_pathplanner.py   # A* with fire avoidance cost injection
│   │   └── agent_vision.py        # Raycasting visibility and danger detection
│   ├── simulation/
│   │   ├── simulation.py          # Main simulation loop and event handling
│   │   ├── sim_renderer.py        # pygame rendering (grid, agents, panel)
│   │   └── sim_analytics.py       # Metrics, snapshots, CSV export
│   ├── building.py                # Multi-floor building container
│   └── grid.py                    # Grid and numpy array management
├── editor/
│   └── editor.py                  # Layout editor (draw walls, place exits, fire sources)
├── environment/
│   ├── fire.py                    # Fire spread, ignition, temperature update
│   └── smoke.py                   # Fick's law smoke diffusion
├── sim_statistics/
│   ├── survival_heatmap.py        # Monte Carlo survival probability heatmap
│   └── congestion_map.py          # Monte Carlo bottleneck / traffic analysis
├── utils/
│   ├── utilities.py               # Constants, enums, helpers
│   ├── save_manager.py            # JSON snapshot persistence
│   ├── time_manager.py            # FPS, step size, pause/step-by-step control
│   └── stairwell_manager.py       # Stairwell ID registry
├── ui/
│   └── slider.py                  # pygame-gui control panel
├── data/
│   ├── layout_csv/                # Layout CSV files (layout_1.csv, layout_2.csv, ...)
│   └── layout_images/             # Optional background images for layouts
├── tests/                         # pytest test suite (76 tests)
├── benchmark.py                   # cProfile-based performance benchmark
└── requirements.txt
```

---

## Running the Simulation

```bash
python main.py
```

On launch, the editor opens with the last used layout. Design your layout then press **E** from the simulation, or simply close the editor to begin. The program loops between editor and simulation modes until you quit.

### Simulation Controls

<img alt="Simulation panel" src="https://github.com/user-attachments/assets/8537d0a8-e344-4b85-899a-43ce11fcfaa2" />

| Key | Action |
|-----|--------|
| `P` / `Space` | Pause / Resume |
| `S` | Toggle step-by-step mode |
| `N` | Advance one step (in step mode) |
| `+` / `-` | Increase / decrease simulation speed |
| `R` | Reset simulation |
| `E` | Return to editor |
| `M` | Cycle to next floor |
| `H` | Toggle controls / metrics panel |
| `F5` | Save JSON snapshot |
| `F6` | Export history CSV |
| `F7` | Load latest snapshot metadata |
| `F8` | Open file picker and launch survival heatmap |
| `F9` | Open file picker and launch congestion map |
| `ESC` | Quit |

---

## Layout Editor

<img alt="Layout editor" src="https://github.com/user-attachments/assets/075011d4-04d4-459b-be87-c69133cadf5c" />

The editor lets you paint cells on the grid before running a simulation.

| Tool | Description |
|------|-------------|
| **Wall (Concrete)** | Non-combustible barrier |
| **Wood** | Combustible wall / furniture |
| **Metal** | Heat-conducting non-combustible cell |
| **Start** | Agent spawn point (up to 3 per layout) |
| **End / Exit** | Evacuation target — required for simulation and statistics |
| **Fire Source** | Cell that ignites at simulation start |
| **Stairwell** | Inter-floor connection point |

Layouts are saved as CSV files in `data/layout_csv/`. Up to 3 start cells can be placed; each spawns one agent with an automatically assigned vulnerability profile.

> **Note:** Every layout must have at least one **End** cell before running the statistics scripts. Both `survival_heatmap.py` and `congestion_map.py` will exit with a clear error message if no exit is found.

---

## Materials

| Material | Ignition (°C) | Fuel | Smoke Yield | Notes |
|----------|--------------|------|-------------|-------|
| Air / Furnishings | 300 | 0.3 | 0.5 | Default open cell |
| Wood | 250 | 5.0 | 1.0 | Burns vigorously |
| Concrete (Wall) | 1500 | 0.0 | 0.0 | Non-combustible barrier |
| Metal | 1500 | 0.0 | 0.0 | High heat conductivity |

---

## Agent Vulnerability Profiles

Each agent is assigned a profile that scales FED accumulation rate and base walking speed.

| Profile | FED Scale | Speed Scale | Notes |
|---------|-----------|-------------|-------|
| `adult_fit` | 1.00 | 1.00 | Baseline |
| `adult_average` | 1.15 | 0.90 | Default |
| `elderly` | 1.50 | 0.65 | High vulnerability |
| `child` | 1.30 | 0.75 | |
| `injured` | 1.80 | 0.50 | Slowest, most vulnerable |

In a 3-agent simulation the profiles are assigned round-robin from this list.

---

## Statistics Scripts

Both scripts run headlessly (no display window) and use multiprocessing for speed. Each scenario places fire at a random valid location, runs a full simulation, and aggregates results across all scenarios.

> Run these from the **project root directory**, not from inside `sim_statistics/`.

### Survival Heatmap

Shows the probability of surviving evacuation from every cell in the layout.

```bash
python -m sim_statistics.survival_heatmap --csv data/layout_csv/layout_1.csv
```

Output saved to `sim_statistics/heatmap/heatmap_<layout_name>.png`.

| Flag | Default | Description |
|------|---------|-------------|
| `--scenarios` | 50 | Number of Monte Carlo runs |
| `--steps` | 200 | Simulation steps per scenario |
| `--dt` | 0.1 | Seconds per step |
| `--workers` | 0 (= cpu count) | Worker processes |
| `--no-mp` | — | Disable multiprocessing |
| `--output` | auto-named | Override output path |

### Congestion / Bottleneck Map

Identifies cells that are both heavily trafficked and environmentally dangerous — the critical chokepoints in the evacuation route.

```bash
python -m sim_statistics.congestion_map --csv data/layout_csv/layout_1.csv
```

Output saved to `sim_statistics/congestion/congestion_<layout_name>.png`. The script also prints the top-10 chokepoint cell coordinates to the terminal.

The output is a 2-panel PNG:

- **Left** — agent traffic frequency (how often each cell was visited)
- **Right** — chokepoint score (traffic × danger), with top-10 worst cells marked

Flags are identical to the survival heatmap.

---

## Data Export

During or after a simulation run:

- **`F5` — JSON Snapshot**: Saves full simulation state including agent trails, fire timeline, all metrics, and parameters to the project root.
- **`F6` — History CSV**: Exports the time-series metrics buffer with columns: `time`, `fire_cells`, `avg_temp`, `avg_smoke`, `agent_health`, `path_length`.

Snapshots are named `simulation_<timestamp>.json`. The latest can be loaded back via `F7` (currently loads metadata only; full state restore is not yet implemented).

---

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_fire_physics.py

# By keyword
pytest -k "smoke and not decay"

# With coverage
pytest --cov=core --cov=environment --cov=utils --cov-report=html
```

### Test Suite (76 tests)

| File | Tests | Covers |
|------|-------|--------|
| `test_agent_state.py` | 14 | State machine (IDLE → REACTION → MOVING), FED damage |
| `test_fire_physics.py` | 10 | Heat diffusion, ignition, fuel consumption, material flammability |
| `test_grid_spot.py` | 24 | Spot states, Grid init, material cache, numpy sync, backup/restore |
| `test_pathfinding.py` | 9 | A\* to exits, wall avoidance, blocked paths, dynamic replanning |
| `test_reset.py` | 13 | Building construction, grid backup/restore, fuel reset regression |
| `test_smoke.py` | 6 | Smoke production, Fick's law diffusion, barrier blocking, decay |

---

## Performance Benchmarking

```bash
python benchmark.py
```

Runs the simulation for 10 seconds under cProfile and writes a ranked function call report to `benchmark_results.txt`. The hottest path (from the last run) is `spot.update_temperature_from_flux` at ~1.8s cumulative, followed by `spot.is_fire` and `spot.draw`.

---

## Physics Notes

**Fire spread** uses a probabilistic cellular automaton. At each step, burning cells transfer heat to neighbours via Fourier's law scaled by material thermal conductivity. A neighbour ignites when its temperature exceeds its material ignition threshold and a uniform random draw is below `FIRE_SPREAD_PROBABILITY` (default 0.3).

**Smoke** diffuses via a discretised Fick's law applied to the `smoke_np` numpy array. Barriers block diffusion entirely. Smoke decays at a configurable rate and is produced proportional to the material's `smoke_yield`.

**FED model** — agents accumulate two independent dose counters: toxic (smoke proxy, linear with smoke density) and thermal (exponential above 60 °C). Incapacitation occurs when either reaches 1.0. Health is derived as `100 × (1 − FED^0.7)` giving a concave decay curve.

**Pathfinding** — A\* with an 8-directional neighbourhood. The heuristic is Euclidean distance. Fire avoidance cost is added as a precomputed inverse-square repulsion grid rebuilt lazily on each vision update, keeping the per-node cost at O(1) during search.