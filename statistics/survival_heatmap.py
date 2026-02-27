"""
    python -m statistics.survival_heatmap --csv data/layout_csv/layout_1.csv
    OR
    python -m statistics.survival_heatmap --csv data/layout_csv/layout_1.csv \
        --scenarios 10 --steps 200 --dt 0.1 --workers 0 --output heatmap.png
"""
#using python -m runs the script as a module, allowing relative imports from the project structure
import argparse
import logging
import os
import sys
import multiprocessing as mp
from collections import deque
from typing import List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

# Headless pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
np.seterr(divide="ignore", invalid="ignore")

# Project imports\
from core.grid import Grid
from environment.fire import randomfirespot, update_fire_with_materials, do_temperature_update

from environment.smoke import spread_smoke
from utils.utilities import load_layout, Dimensions, state_value, material_id, rTemp

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
ROWS  = Dimensions.ROWS.value
WIDTH = Dimensions.WIDTH.value

# Grid helpers
def build_fresh_grid(csv_path: str) -> Grid:
    grid = Grid(ROWS, WIDTH)
    start_spots, end_spots = load_layout(grid.grid, csv_path)
    grid.start = start_spots
    grid.exits = set(end_spots)
    for spot in end_spots:
        grid.add_exit(spot)
    grid.mark_material_cache_dirty()
    grid.ensure_material_cache()
    grid.backup_layout()
    return grid

def restore_grid(grid: Grid) -> None:
    if grid.initial_layout is None:
        return
    for r, row_data in enumerate(grid.initial_layout):
        for c, d in enumerate(row_data):
            spot = grid.grid[r][c]
            spot.reset()
            mat = d["material"]
            st  = d["state"]
            if st == state_value.WALL.value:
                spot.make_barrier()
            elif st == state_value.START.value:
                spot.make_start()
            elif st == state_value.END.value:
                spot.make_end()
            elif st == state_value.FIRE.value:
                spot.set_on_fire()
            else:
                try:
                    spot.set_material(
                        material_id(mat.value if hasattr(mat, "value") else mat)
                    )
                except (ValueError, KeyError):
                    pass
            spot._temperature    = d["temperature"]
            spot._smoke          = d["smoke"]
            spot._fuel           = d["fuel"]
            spot._is_fire_source = d["is_fire_source"]
            spot._burned         = False
    grid.start  = [s for row in grid.grid for s in row if s.is_start()]
    grid.exits  = {s for row in grid.grid for s in row if s.is_end()}
    grid.fire_sources.clear()
    grid.temp_np[:]   = 0
    grid.smoke_np[:]  = 0
    grid.fuel_np[:]   = 0
    grid.fire_np[:]   = False
    grid.burned_np[:] = False
    grid.mark_material_cache_dirty()
    grid.ensure_material_cache()

def place_fire(grid: Grid) -> bool:
    placed = randomfirespot(grid, ROWS, max_dist=30)
    if placed:
        for r, c in list(grid.fire_sources):
            spot = grid.grid[r][c]
            if not spot.is_barrier() and not spot.is_start() and not spot.is_end():
                spot.set_as_fire_source(temp=1200.0)
    return placed

# Fire snapshot
FireSnapshot = List[Tuple[np.ndarray, np.ndarray, np.ndarray]]

def build_fire_snapshot(grid: Grid, steps: int, dt: float) -> FireSnapshot:
    snapshots: FireSnapshot = []
    for _ in range(steps):
        update_fire_with_materials(grid, dt)
        do_temperature_update(grid, dt)
        spread_smoke(grid, dt)
        grid.update_np_arrays()
        snapshots.append((
            grid.temp_np.copy(),
            grid.smoke_np.copy(),
            grid.fire_np.copy(),
        ))
    return snapshots

# Vectorised BFS - runs once per scenario, not once per cell
def bfs_distance(barrier_mask: np.ndarray, exit_mask: np.ndarray) -> np.ndarray:
    """Multi-source BFS from all exits. Returns distance array."""
    dist = np.full((ROWS, ROWS), np.inf, dtype=np.float32)
    q = deque()
    for r, c in np.argwhere(exit_mask):
        dist[r, c] = 0.0
        q.append((int(r), int(c)))

    MOVES = [(-1,-1,1.414),(-1,0,1.0),(-1,1,1.414), #sqrt2 costs for diagonals
              (0,-1,1.0),              (0,1,1.0),
              (1,-1,1.414),(1,0,1.0), (1,1,1.414)]

    while q:
        r, c = q.popleft()
        d = dist[r, c]
        for dr, dc, cost in MOVES:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < ROWS and not barrier_mask[nr, nc]:
                nd = d + cost
                if nd < dist[nr, nc]:
                    dist[nr, nc] = nd
                    q.append((nr, nc))
    return dist

def compute_next_move(
    barrier_mask: np.ndarray,
    fire_mask: np.ndarray,
    smoke_arr: np.ndarray,
    temp_arr: np.ndarray,
    exit_mask: np.ndarray,
) -> np.ndarray:
    """
    For every cell compute which neighbour minimises (distance_to_exit + danger).
    Returns (ROWS, ROWS, 2) int8 array of (dr, dc).
    Runs in O(8 * ROWS^2) numpy ops - called ~every 10 steps.
    """
    blocked   = barrier_mask | fire_mask
    base_dist = bfs_distance(blocked, exit_mask)

    danger = smoke_arr * 12.0 + np.maximum(0.0, (temp_arr - 60.0) * 0.8)

    MOVES = [(-1,-1,1.414),(-1,0,1.0),(-1,1,1.414),
              (0,-1,1.0),              (0,1,1.0),
              (1,-1,1.414),(1,0,1.0), (1,1,1.414)]

    best_score = np.full((ROWS, ROWS), np.inf, dtype=np.float32)
    next_dr    = np.zeros((ROWS, ROWS), dtype=np.int8)
    next_dc    = np.zeros((ROWS, ROWS), dtype=np.int8)

    r_idx = np.arange(ROWS, dtype=np.int32)[:, None]
    c_idx = np.arange(ROWS, dtype=np.int32)[None, :]

    for dr, dc, move_cost in MOVES:
        nr = r_idx + dr
        nc = c_idx + dc
        valid = (nr >= 0) & (nr < ROWS) & (nc >= 0) & (nc < ROWS)
        nr_c  = np.clip(nr, 0, ROWS-1).astype(np.int32)
        nc_c  = np.clip(nc, 0, ROWS-1).astype(np.int32)

        n_blocked = np.where(valid, blocked[nr_c, nc_c], True)
        n_dist    = np.where(valid & ~n_blocked, base_dist[nr_c, nc_c], np.inf)
        n_danger  = np.where(valid & ~n_blocked, danger[nr_c, nc_c],    0.0)
        score     = n_dist + n_danger * 0.3

        better = score < best_score
        best_score = np.where(better, score, best_score)
        next_dr    = np.where(better, dr, next_dr).astype(np.int8)
        next_dc    = np.where(better, dc, next_dc).astype(np.int8)

    return np.stack([next_dr, next_dc], axis=-1)

# Batch agent simulator - all N candidates advance in one numpy call
class BatchAgentSim:
    SPEED_CLEAR  = 3.67
    SPEED_SLIGHT = 0.96
    SPEED_HEAVY  = 0.64
    SMOKE_SLIGHT = 0.13
    SMOKE_HEAVY  = 0.50

    def __init__(
        self,
        cands_r: np.ndarray, #cands_r and cands_c are the initial positions of all valid candidate positions for agents
        cands_c: np.ndarray,
        barrier_mask: np.ndarray,
        exit_mask: np.ndarray,
        cell_size_m: float = 0.5,
        base_speed:  float = 1.0,
    ) -> None:
        N = len(cands_r)
        self.pos_r          = cands_r.copy().astype(np.int32)
        self.pos_c          = cands_c.copy().astype(np.int32)
        self.health         = np.full(N, 100.0,  dtype=np.float32)
        self.alive          = np.ones(N,          dtype=bool)
        self.escaped        = np.zeros(N,         dtype=bool)
        self.state_idx      = np.zeros(N,         dtype=np.int8)   # 0=IDLE 1=REACT 2=MOVE
        self.reaction_timer = np.full(N,  2.0,   dtype=np.float32)
        self.move_timer     = np.zeros(N,         dtype=np.float32)
        self.barrier_mask   = barrier_mask
        self.exit_mask      = exit_mask
        self.cell_size_m    = cell_size_m
        self.base_speed     = base_speed
        self._next_move: Optional[np.ndarray] = None
        self._last_fire_hash: Optional[int]   = None

    def _refresh_pathfinding(self, fire_arr, smoke_arr, temp_arr) -> None:
        self._next_move = compute_next_move(
            self.barrier_mask, fire_arr, smoke_arr, temp_arr, self.exit_mask
        )
        self._last_fire_hash = hash(fire_arr.tobytes())

    def step(self, snap: Tuple, dt: float, step_idx: int) -> None:
        temp_arr, smoke_arr, fire_arr = snap

        fhash = hash(fire_arr.tobytes())
        if fhash != self._last_fire_hash or step_idx % 10 == 0:
            self._refresh_pathfinding(fire_arr, smoke_arr, temp_arr)

        r, c   = self.pos_r, self.pos_c
        s_smk  = smoke_arr[r, c]
        s_tmp  = temp_arr[r, c]
        s_fire = fire_arr[r, c]
        on_exit = self.exit_mask[r, c]

        active = self.alive & ~self.escaped

        # Escaped?
        self.escaped |= active & on_exit
        active &= ~self.escaped

        # Instant death from fire
        burned = active & s_fire
        self.health[burned] = 0
        self.alive[burned]  = False
        active &= ~burned

        # Health damage
        dmg = (s_smk * 5.0 + np.maximum(0.0, s_tmp - 50.0) * 0.3) * dt
        self.health[active] -= dmg[active]
        dead = active & (self.health <= 0)
        self.alive[dead] = False
        active &= ~dead

        # State machine
        idle_with_smoke = active & (self.state_idx == 0) & (s_smk > 0.2)
        self.state_idx[idle_with_smoke] = 1

        reacting = active & (self.state_idx == 1)
        self.reaction_timer[reacting] -= dt
        self.state_idx[reacting & (self.reaction_timer <= 0)] = 2

        # Movement
        moving = active & (self.state_idx == 2)
        self.move_timer[moving] += dt

        interval = np.where(
            s_smk < self.SMOKE_SLIGHT,
            self.cell_size_m / (self.SPEED_CLEAR  * self.base_speed),
            np.where(
                s_smk < self.SMOKE_HEAVY,
                self.cell_size_m / (self.SPEED_SLIGHT * self.base_speed),
                self.cell_size_m / (self.SPEED_HEAVY  * self.base_speed),
            )
        )

        can_move_mask = moving & (self.move_timer >= interval)
        if np.any(can_move_mask):
            idx  = np.where(can_move_mask)[0]
            cr   = r[idx]
            cc   = c[idx]
            dr   = self._next_move[cr, cc, 0].astype(np.int32)
            dc   = self._next_move[cr, cc, 1].astype(np.int32)
            nr   = np.clip(cr + dr, 0, ROWS-1)
            nc   = np.clip(cc + dc, 0, ROWS-1)
            ok   = ~self.barrier_mask[nr, nc] & ~fire_arr[nr, nc]
            self.pos_r[idx[ok]] = nr[ok]
            self.pos_c[idx[ok]] = nc[ok]
            self.move_timer[can_move_mask] = 0.0

    def survived(self) -> np.ndarray:
        return self.escaped | (self.alive & (self.health > 0))

# Single scenario runner
def run_scenario(
    grid: Grid,
    cands_r: np.ndarray,
    cands_c: np.ndarray,
    barrier_mask: np.ndarray,
    exit_mask: np.ndarray,
    steps: int,
    dt: float,
) -> np.ndarray:
    restore_grid(grid)
    if not place_fire(grid):
        return np.ones(len(cands_r), dtype=bool)

    snapshots = build_fire_snapshot(grid, steps, dt)

    cfg = rTemp()
    sim = BatchAgentSim(
        cands_r, cands_c, barrier_mask, exit_mask,
        cell_size_m=cfg.CELL_SIZE_M,
        base_speed=cfg.BASE_SPEED_M_S,
    )
    for i, snap in enumerate(snapshots):
        sim.step(snap, dt, i)
        if not np.any(sim.alive & ~sim.escaped):
            break

    return sim.survived()

# Multiprocessing worker
_w_grid: Optional[Grid]     = None
_w_barrier: Optional[np.ndarray] = None
_w_exit:    Optional[np.ndarray] = None
_w_cands_r: Optional[np.ndarray] = None
_w_cands_c: Optional[np.ndarray] = None
_w_steps: int  = 200
_w_dt:    float = 0.1

def _worker_init_v3(csv_path: str, steps: int, dt: float) -> None:
    global _w_grid, _w_barrier, _w_exit, _w_cands_r, _w_cands_c, _w_steps, _w_dt
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame as _pg
    _pg.init()
    _pg.display.set_mode((1, 1), _pg.NOFRAME)
    np.seterr(divide="ignore", invalid="ignore")

    _w_steps = steps
    _w_dt    = dt
    _w_grid  = build_fresh_grid(csv_path)

    _w_barrier = np.array(
        [[_w_grid.grid[r][c].is_barrier() for c in range(ROWS)] for r in range(ROWS)],
        dtype=bool,
    )
    _w_exit = np.array(
        [[_w_grid.grid[r][c].is_end() for c in range(ROWS)] for r in range(ROWS)],
        dtype=bool,
    )
    coords = [
        (r, c) for r in range(ROWS) for c in range(ROWS)
        if not _w_barrier[r, c] and not _w_exit[r, c]
    ]
    _w_cands_r = np.array([x[0] for x in coords], dtype=np.int32)
    _w_cands_c = np.array([x[1] for x in coords], dtype=np.int32)

def _worker_fn_v3(scenario_idx: int) -> Tuple[int, np.ndarray]:
    survived = run_scenario(
        _w_grid, _w_cands_r, _w_cands_c,
        _w_barrier, _w_exit, _w_steps, _w_dt,
    )
    return scenario_idx, survived

# Main builder
def build_heatmap(
    csv_path: str,
    scenarios: int = 5,
    steps: int = 200,
    dt: float = 0.1,
    workers: int = 0,
    use_mp: bool = True,
) -> np.ndarray:

    probe = build_fresh_grid(csv_path)
    barrier_mask = np.array(
        [[probe.grid[r][c].is_barrier() for c in range(ROWS)] for r in range(ROWS)],
        dtype=bool,
    )
    exit_mask = np.array(
        [[probe.grid[r][c].is_end() for c in range(ROWS)] for r in range(ROWS)],
        dtype=bool,
    )
    coords = [
        (r, c) for r in range(ROWS) for c in range(ROWS)
        if not barrier_mask[r, c] and not exit_mask[r, c]
    ]
    cands_r = np.array([x[0] for x in coords], dtype=np.int32)
    cands_c = np.array([x[1] for x in coords], dtype=np.int32)
    N = len(coords)

    n_workers = min(workers if workers > 0 else mp.cpu_count(), scenarios)
    print(f"Cells    : {N}  (all tested simultaneously per scenario)")
    print(f"Scenarios: {scenarios}")
    print(f"Steps    : {steps}  ({steps * dt:.1f}s simulated)")
    print(f"Workers  : {n_workers if use_mp else 1}\n")

    survival_counts = np.zeros(N, dtype=np.int32)

    if use_mp and n_workers > 1:
        ctx = mp.get_context("spawn")
        with ctx.Pool(
            processes=n_workers,
            initializer=_worker_init_v3,
            initargs=(csv_path, steps, dt),
        ) as pool:
            for _, survived in tqdm(
                pool.imap_unordered(_worker_fn_v3, range(scenarios)),
                total=scenarios, desc="Scenarios", unit="scenario",
            ):
                survival_counts += survived.astype(np.int32)
    else:
        _worker_init_v3(csv_path, steps, dt)
        for i in tqdm(range(scenarios), desc="Scenarios", unit="scenario"):
            _, survived = _worker_fn_v3(i)
            survival_counts += survived.astype(np.int32)

    survival = np.full((ROWS, ROWS), np.nan, dtype=np.float32)
    for idx, (r, c) in enumerate(coords):
        survival[r, c] = survival_counts[idx] / scenarios #probability of survival at this cell across all scenarios
    return survival

# Plot
def plot_heatmap(survival: np.ndarray, output_path: str, csv_path: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 10))
    bg = np.where(np.isnan(survival), 0.5, np.nan)
    ax.imshow(bg, cmap="Greys", vmin=0, vmax=1, interpolation="nearest", alpha=0.4)
    im = ax.imshow(survival, cmap=plt.cm.RdYlGn, vmin=0.0, vmax=1.0,
                   interpolation="nearest", alpha=0.9)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Survival Probability", fontsize=13)
    ax.set_title(f"Agent Survival Probability Heatmap\nLayout: {os.path.basename(csv_path)}",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Column", fontsize=11)
    ax.set_ylabel("Row", fontsize=11)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Heatmap saved  -> {output_path}")

# CLI
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Headless survival heatmap (v3 vectorised)")
    p.add_argument("--csv",       required=True)
    p.add_argument("--scenarios", type=int,   default=50) #number of times to run a full simulation with random fire placement - more runs = smoother heatmap but longer runtime
    p.add_argument("--steps",     type=int,   default=200)
    p.add_argument("--dt",        type=float, default=0.1)
    p.add_argument("--workers",   type=int,   default=0)
    p.add_argument("--output",    default="survival_heatmap.png")
    p.add_argument("--no-mp",     action="store_true")
    return p.parse_args()
def main() -> None:
    args = parse_args()
    if not os.path.exists(args.csv):
        sys.exit(f"ERROR: CSV not found: {args.csv}")

    # Extract layout number or base name for output
    base_name = os.path.splitext(os.path.basename(args.csv))[0]  # e.g., layout_1
    output_dir = "statistics/heatmap"  # folder to save heatmaps
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"heatmap_{base_name}.png")

    print(f"Layout  : {args.csv}\nOutput  : {output_path}\n")
    survival = build_heatmap(
        csv_path=args.csv, scenarios=args.scenarios,
        steps=args.steps, dt=args.dt,
        workers=args.workers, use_mp=not args.no_mp,
    )
    valid = survival[~np.isnan(survival)]
    print(f"\nSurvival across {len(valid)} cells:")
    print(f"  Mean : {valid.mean():.2%}  Min : {valid.min():.2%}  Max : {valid.max():.2%}")
    plot_heatmap(survival, output_path, args.csv)

if __name__ == "__main__":
    main()