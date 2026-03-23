"""
Bottleneck / congestion map for fire evacuation layouts.
Runs N Monte Carlo scenarios and records how often each cell is visited by evacuating agents. Overlays that traffic frequency with average environmental danger (smoke + temperature) to identify critical chokepoints:
cells that are both heavily used AND hazardous.

Usage:
    python -m sim_statistics.congestion_map --csv data/layout_csv/layout_1.csv
"""
# Leftmost graph is the agent traffic frequency map: how many agents passed through each cell across all scenarios (normalised to [0, 1])
# Middle graph is the average environmental danger map: mean of (smoke × 12 + excess temp × 0.8) across all scenarios (normalised to [0, 1])
# Rightmost graph is the chokepoint score map: traffic × danger (high values indicate critical chokepoints with both heavy traffic and high hazard)
import argparse
import logging
import os
import sys
import multiprocessing as mp
from collections import deque
from typing import List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from tqdm import tqdm

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
np.seterr(divide="ignore", invalid="ignore")

from core.grid import Grid
from environment.fire import randomfirespot, update_fire_with_materials, do_temperature_update
from environment.smoke import spread_smoke
from utils.utilities import load_layout, Dimensions, state_value, material_id, rTemp

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

ROWS  = Dimensions.ROWS.value
WIDTH = Dimensions.WIDTH.value


def build_fresh_grid(csv_path: str) -> Grid:
    grid = Grid(ROWS, WIDTH, floor=0)
    start_spots, end_spots = load_layout(grid.grid, csv_path)
    grid.start  = start_spots
    grid.exits  = set(end_spots)
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
                    spot.set_material(material_id(mat.value if hasattr(mat, "value") else mat))
                except (ValueError, KeyError):
                    pass
            spot._temperature    = d["temperature"]
            spot._smoke          = d["smoke"]
            spot._fuel           = d["fuel"]
            spot._is_fire_source = d["is_fire_source"]
            spot._burned         = False
    grid.start        = [s for row in grid.grid for s in row if s.is_start()]
    grid.exits        = {s for row in grid.grid for s in row if s.is_end()}
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

# Pathfinding (Uses BFS to compute distance-to-exit under current conditions, then picks best local move based on that + danger)
def bfs_distance(barrier_mask: np.ndarray, exit_mask: np.ndarray) -> np.ndarray:
    dist = np.full((ROWS, ROWS), np.inf, dtype=np.float32)
    q = deque()
    for r, c in np.argwhere(exit_mask):
        dist[r, c] = 0.0
        q.append((int(r), int(c)))

    MOVES = [(-1,-1,1.414),(-1,0,1.0),(-1,1,1.414),
              (0,-1,1.0),             (0,1,1.0),
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
    blocked   = barrier_mask | fire_mask
    base_dist = bfs_distance(blocked, exit_mask)
    danger    = smoke_arr * 12.0 + np.maximum(0.0, (temp_arr - 60.0) * 0.8)

    MOVES = [(-1,-1,1.414),(-1,0,1.0),(-1,1,1.414),
              (0,-1,1.0),             (0,1,1.0),
              (1,-1,1.414),(1,0,1.0), (1,1,1.414)]

    best_score = np.full((ROWS, ROWS), np.inf, dtype=np.float32)
    next_dr    = np.zeros((ROWS, ROWS), dtype=np.int8)
    next_dc    = np.zeros((ROWS, ROWS), dtype=np.int8)

    r_idx = np.arange(ROWS, dtype=np.int32)[:, None]
    c_idx = np.arange(ROWS, dtype=np.int32)[None, :]

    for dr, dc, move_cost in MOVES:
        nr    = r_idx + dr
        nc    = c_idx + dc
        valid = (nr >= 0) & (nr < ROWS) & (nc >= 0) & (nc < ROWS)
        nr_c  = np.clip(nr, 0, ROWS-1).astype(np.int32)
        nc_c  = np.clip(nc, 0, ROWS-1).astype(np.int32)

        n_blocked = np.where(valid, blocked[nr_c, nc_c], True)
        n_dist    = np.where(valid & ~n_blocked, base_dist[nr_c, nc_c], np.inf)
        n_danger  = np.where(valid & ~n_blocked, danger[nr_c, nc_c],    0.0)
        score     = n_dist + n_danger * 0.3

        better     = score < best_score
        best_score = np.where(better, score, best_score)
        next_dr    = np.where(better, dr, next_dr).astype(np.int8)
        next_dc    = np.where(better, dc, next_dc).astype(np.int8)

    return np.stack([next_dr, next_dc], axis=-1)

# BatchAgentSim    extended to record traffic
class BatchAgentSim:
    """
    Identical movement logic to survival_heatmap.BatchAgentSim, but also
    accumulates a (ROWS, ROWS) traffic grid counting agent-steps per cell.
    """
    SPEED_CLEAR  = 3.67
    SPEED_SLIGHT = 0.96
    SPEED_HEAVY  = 0.64
    SMOKE_SLIGHT = 0.13
    SMOKE_HEAVY  = 0.50

    def __init__(
        self,
        cands_r: np.ndarray,
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
        self.state_idx      = np.zeros(N,         dtype=np.int8)
        self.reaction_timer = np.full(N,  2.0,    dtype=np.float32)
        self.move_timer     = np.zeros(N,         dtype=np.float32)
        self.barrier_mask   = barrier_mask
        self.exit_mask      = exit_mask
        self.cell_size_m    = cell_size_m
        self.base_speed     = base_speed
        self._next_move: Optional[np.ndarray] = None
        self._last_fire_hash: Optional[int]   = None

        # congestion additions 
        # traffic[r, c] = total agent-steps spent at (r, c) across all steps
        self.traffic = np.zeros((ROWS, ROWS), dtype=np.int64)
        # peak_danger[r, c] = max danger score seen at (r, c) while agents occupied it
        self.peak_danger = np.zeros((ROWS, ROWS), dtype=np.float32)

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

        # Record traffic: each active agent stamps its current cell
        if np.any(active):
            np.add.at(self.traffic, (self.pos_r[active], self.pos_c[active]), 1)

            # Record danger at occupied cells
            danger_at_pos = (s_smk * 12.0 + np.maximum(0.0, (s_tmp - 60.0) * 0.8))
            np.maximum.at(self.peak_danger, (self.pos_r[active], self.pos_c[active]),
                          danger_at_pos[active])

        # Standard movement logic (unchanged from survival_heatmap)
        self.escaped |= active & on_exit
        active &= ~self.escaped

        burned = active & s_fire
        self.health[burned] = 0
        self.alive[burned]  = False
        active &= ~burned

        dmg = (s_smk * 5.0 + np.maximum(0.0, s_tmp - 50.0) * 0.3) * dt
        self.health[active] -= dmg[active]
        dead = active & (self.health <= 0)
        self.alive[dead] = False
        active &= ~dead

        idle_with_smoke = active & (self.state_idx == 0) & (s_smk > 0.2)
        self.state_idx[idle_with_smoke] = 1

        reacting = active & (self.state_idx == 1)
        self.reaction_timer[reacting] -= dt
        self.state_idx[reacting & (self.reaction_timer <= 0)] = 2

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
            idx = np.where(can_move_mask)[0]
            cr  = r[idx]
            cc  = c[idx]
            dr  = self._next_move[cr, cc, 0].astype(np.int32)
            dc  = self._next_move[cr, cc, 1].astype(np.int32)
            nr  = np.clip(cr + dr, 0, ROWS - 1)
            nc  = np.clip(cc + dc, 0, ROWS - 1)
            ok  = ~self.barrier_mask[nr, nc] & ~fire_arr[nr, nc]
            self.pos_r[idx[ok]] = nr[ok]
            self.pos_c[idx[ok]] = nc[ok]
            self.move_timer[can_move_mask] = 0.0

# Single scenario runner — returns (traffic_grid, danger_grid)
def run_scenario(
    grid: Grid,
    cands_r: np.ndarray,
    cands_c: np.ndarray,
    barrier_mask: np.ndarray,
    exit_mask: np.ndarray,
    steps: int,
    dt: float,
) -> Tuple[np.ndarray, np.ndarray]:
    restore_grid(grid)
    if not np.any(exit_mask):
        return np.zeros((ROWS, ROWS), dtype=np.int64), np.zeros((ROWS, ROWS), dtype=np.float32)
    if not place_fire(grid):
        return np.zeros((ROWS, ROWS), dtype=np.int64), np.zeros((ROWS, ROWS), dtype=np.float32)

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

    return sim.traffic, sim.peak_danger

# Multiprocessing worker
_w_grid:    Optional[Grid]       = None
_w_barrier: Optional[np.ndarray] = None
_w_exit:    Optional[np.ndarray] = None
_w_cands_r: Optional[np.ndarray] = None
_w_cands_c: Optional[np.ndarray] = None
_w_steps:   int   = 200
_w_dt:      float = 0.1


def _worker_init(csv_path: str, steps: int, dt: float) -> None:
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


def _worker_fn(scenario_idx: int) -> Tuple[int, np.ndarray, np.ndarray]:
    traffic, danger = run_scenario(
        _w_grid, _w_cands_r, _w_cands_c,
        _w_barrier, _w_exit, _w_steps, _w_dt,
    )
    return scenario_idx, traffic, danger

# Main builder

def build_congestion_map(
    csv_path: str,
    scenarios: int = 50,
    steps: int = 200,
    dt: float = 0.1,
    workers: int = 0,
    use_mp: bool = True,
    gui_mode: bool = False, # ADDED
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns:
        barrier_mask  (ROWS, ROWS) bool   — walls / non-walkable cells
        total_traffic (ROWS, ROWS) int64  — sum of agent-steps per cell
        avg_danger    (ROWS, ROWS) float  — mean peak danger per cell
    """
    probe = build_fresh_grid(csv_path)
    barrier_mask = np.array(
        [[probe.grid[r][c].is_barrier() for c in range(ROWS)] for r in range(ROWS)],
        dtype=bool,
    )
    exit_mask = np.array(
        [[probe.grid[r][c].is_end() for c in range(ROWS)] for r in range(ROWS)],
        dtype=bool,
    )
    if not np.any(exit_mask):
        sys.exit(f"ERROR: No exit cells found in {csv_path}. "
                "Mark at least one cell as END in the editor before running this analysis.")
    coords = [
        (r, c) for r in range(ROWS) for c in range(ROWS)
        if not barrier_mask[r, c] and not exit_mask[r, c]
    ]
    cands_r = np.array([x[0] for x in coords], dtype=np.int32)
    cands_c = np.array([x[1] for x in coords], dtype=np.int32)

    n_workers = min(workers if workers > 0 else mp.cpu_count(), scenarios)
    if not gui_mode:
        print(f"Cells    : {len(coords)}  (all seeded simultaneously per scenario)")
        print(f"Scenarios: {scenarios}")
        print(f"Steps    : {steps}  ({steps * dt:.1f}s simulated)")
        print(f"Workers  : {n_workers if use_mp else 1}\n")

    total_traffic = np.zeros((ROWS, ROWS), dtype=np.int64)
    sum_danger    = np.zeros((ROWS, ROWS), dtype=np.float64)

    if use_mp and n_workers > 1:
        ctx = mp.get_context("spawn")
        with ctx.Pool(
            processes=n_workers,
            initializer=_worker_init,
            initargs=(csv_path, steps, dt),
        ) as pool:
            iterator = pool.imap_unordered(_worker_fn, range(scenarios))
            if not gui_mode:
                iterator = tqdm(iterator, total=scenarios, desc="Scenarios", unit="scenario")
            
            for i, (_, traffic, danger) in enumerate(iterator):
                total_traffic += traffic
                sum_danger    += danger
                if gui_mode:
                    print(f"PROGRESS:{i+1}/{scenarios}", flush=True)
    else:
        _worker_init(csv_path, steps, dt)
        iterator = range(scenarios)
        if not gui_mode:
            iterator = tqdm(iterator, desc="Scenarios", unit="scenario")
            
        for i in iterator:
            _, traffic, danger = _worker_fn(i)
            total_traffic += traffic
            sum_danger    += danger
            if gui_mode:
                print(f"PROGRESS:{i+1}/{scenarios}", flush=True)

    avg_danger = (sum_danger / scenarios).astype(np.float32)
    return barrier_mask, total_traffic, avg_danger

# Plotting
def plot_congestion_map(
    barrier_mask: np.ndarray,
    total_traffic: np.ndarray,
    avg_danger: np.ndarray,
    output_path: str,
    csv_path: str,
    gui_mode: bool = False, # ADDED
) -> None:
    layout_name = os.path.basename(csv_path)

    # Normalise traffic to [0, 1] for visualisation
    traffic_f = total_traffic.astype(np.float32)
    t_max = traffic_f.max()
    if t_max > 0:
        traffic_norm = traffic_f / t_max
    else:
        traffic_norm = traffic_f

    # Danger: normalise independently
    d_max = avg_danger.max()
    danger_norm = avg_danger / d_max if d_max > 0 else avg_danger.copy()

    # Chokepoint score = traffic_norm * danger_norm (high on both axes)
    choke = traffic_norm * danger_norm

    # Mask walls as NaN so imshow leaves them grey
    def masked(arr: np.ndarray) -> np.ndarray:
        out = arr.copy().astype(np.float32)
        out[barrier_mask] = np.nan
        return out
    
    # fig, axes = plt.subplots(1, 3, figsize=(18, 6)) #for traffic, danger, chokepoint
    fig, axes = plt.subplots(1, 2, figsize=(12, 6)) # for traffic and chokepoint only 
    fig.suptitle(
        f"Evacuation Congestion & Bottleneck Analysis\nLayout: {layout_name}",
        fontsize=14, fontweight="bold",
    )

    wall_cmap = plt.cm.Greys
    wall_cmap.set_bad(color="#888888")  # walls rendered as mid-grey

    # Panel 1: Traffic frequency
    ax = axes[0]
    im0 = ax.imshow(masked(traffic_norm), cmap="YlOrRd", vmin=0, vmax=1,
                    interpolation="nearest")
    fig.colorbar(im0, ax=ax, fraction=0.046, pad=0.04).set_label("Relative Traffic", fontsize=10)
    ax.set_title("Agent Traffic Frequency\n(brighter = more agents passed through)", fontsize=10)
    ax.set_xlabel("Column"); ax.set_ylabel("Row")
    
    # # Panel 2: Environmental danger
    # ax = axes[1]
    # im1 = ax.imshow(masked(danger_norm), cmap="RdPu", vmin=0, vmax=1,
    #                 interpolation="nearest")
    # fig.colorbar(im1, ax=ax, fraction=0.046, pad=0.04).set_label("Relative Danger", fontsize=10)
    # ax.set_title("Average Env. Danger\n(smoke × 12 + excess temp × 0.8, normalised)", fontsize=10)
    # ax.set_xlabel("Column"); ax.set_ylabel("Row")
    
    # Panel 3: Chokepoint overlay
    # ax = axes[2] # enable for all 3 panels
    ax = axes[1]
    # Grey background for walls
    ax.imshow(barrier_mask.astype(np.float32), cmap="Greys", vmin=0, vmax=1,
              interpolation="nearest", alpha=0.4)
    # Chokepoint score on top
    choke_masked = masked(choke)
    im2 = ax.imshow(choke_masked, cmap="hot", vmin=0, vmax=choke_masked[~np.isnan(choke_masked)].max() if np.any(~np.isnan(choke_masked)) else 1,
                    interpolation="nearest", alpha=0.9)
    cbar = fig.colorbar(im2, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Chokepoint Score (traffic × danger)", fontsize=10)
    ax.set_title("Critical Chokepoints\n(high traffic AND high hazard)", fontsize=10)
    ax.set_xlabel("Column"); ax.set_ylabel("Row")

    # Mark top-10 chokepoint cells with a white dot
    flat = choke_masked.copy()
    flat[np.isnan(flat)] = -1
    top_idx = np.argsort(flat.ravel())[::-1][:10]
    top_r, top_c = np.unravel_index(top_idx, flat.shape)
    valid = flat[top_r, top_c] > 0
    ax.scatter(top_c[valid], top_r[valid], s=60, c="white", edgecolors="black",
               linewidths=0.8, zorder=5, label="Top-10 chokepoints")
    ax.legend(loc="lower right", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    
    if not gui_mode:
        print(f"Congestion map saved -> {output_path}")

# CLI
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evacuation bottleneck / congestion map")
    p.add_argument("--csv",       required=True,  help="Path to layout CSV")
    p.add_argument("--scenarios", type=int,   default=50,  help="Monte Carlo runs (default 50)")
    p.add_argument("--steps",     type=int,   default=200, help="Steps per scenario (default 200)")
    p.add_argument("--dt",        type=float, default=0.1, help="Seconds per step (default 0.1)")
    p.add_argument("--workers",   type=int,   default=0,   help="Worker processes; 0=cpu_count")
    p.add_argument("--output",    default="",              help="Output PNG (auto-named if empty)")
    p.add_argument("--no-mp",     action="store_true",     help="Disable multiprocessing")
    p.add_argument("--gui-mode",  action="store_true",     help="Format output for Pygame GUI parser") # ADDED
    return p.parse_args()

def main() -> None:
    args = parse_args()
    if not os.path.exists(args.csv):
        sys.exit(f"ERROR: CSV not found: {args.csv}")

    base_name  = os.path.splitext(os.path.basename(args.csv))[0]
    output_dir = "sim_statistics/congestion"
    os.makedirs(output_dir, exist_ok=True)
    output_path = args.output or os.path.join(output_dir, f"congestion_{base_name}.png")

    if not args.gui_mode:
        print(f"Layout  : {args.csv}\nOutput  : {output_path}\n")

    barrier_mask, total_traffic, avg_danger = build_congestion_map(
        csv_path=args.csv,
        scenarios=args.scenarios,
        steps=args.steps,
        dt=args.dt,
        workers=args.workers,
        use_mp=not args.no_mp,
        gui_mode=args.gui_mode # PASSED
    )

    if not args.gui_mode:
        walkable = ~barrier_mask
        t = total_traffic[walkable]
        print(f"\nTraffic across {walkable.sum()} walkable cells:")
        print(f"  Mean: {t.mean():.1f}  Median: {np.median(t):.1f}  Max: {t.max()}")

    plot_congestion_map(barrier_mask, total_traffic, avg_danger, output_path, args.csv, gui_mode=args.gui_mode)

    # Signal completion to the Pygame UI
    if args.gui_mode:
        print(f"DONE:{output_path}", flush=True)

if __name__ == "__main__":
    main()