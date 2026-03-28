# Testing Guide

## Quick Start

```bash
# Run from project root
cd "d:\Python\fire simulation\Pre-FIRE"

# Run all tests
pytest

# Short summary
pytest -q
```

## Running Specific Tests

### By file

```bash
pytest tests/*.py
eg: pytest tests/test_agent_state.py
```

### By class

```bash
pytest tests/*.py::ClassName
eg: pytest tests/test_grid_spot.py::TestSpotState
```

### By individual test

```bash
pytest tests/*.py::ClassName::TestName
eg: pytest tests/test_reset.py::TestAgentReset::test_reset_spot_is_single_spot
```

### By keyword match (`-k`)

```bash
# Run all tests with "fire" in the name
pytest -k fire

# Run all tests with "reset" but not "fuel"
pytest -k "reset and not fuel"

# Run all damage-related tests
pytest -k damage
```

## Useful Flags

| Flag | Purpose |
|------|---------|
| `-v` | Verbose output (show each test name) |
| `-q` | Quiet output (just pass/fail count) |
| `-x` | Stop on first failure |
| `--lf` | Re-run only last failed tests |
| `--ff` | Run failed tests first, then the rest |
| `-s` | Show print/stdout output from tests |
| `--tb=long` | Full tracebacks on failure |
| `--tb=no` | No tracebacks |
| `--co` | List tests without running them |

### Examples

```bash
# Stop at first failure with full traceback
pytest -x --tb=long

# Re-run only tests that failed last time
pytest --lf

# List all tests without running
pytest --co -q

# Show print statements during tests
pytest -s tests/test_smoke.py
```

## Test Coverage

```bash
# Install coverage plugin
pip install pytest-cov

# Run with coverage report
pytest --cov=core --cov=environment --cov=utils

# Generate HTML report
pytest --cov=core --cov=environment --cov=utils --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Overview (76 tests)

### test_agent_state.py (14 tests)
Agent state machine (IDLE → REACTION → MOVING) and damage mechanics (fire, smoke, heat).

### test_fire_physics.py (10 tests)
Heat diffusion (Fourier's law), fire ignition, fuel consumption, material flammability.

### test_grid_spot.py (24 tests)
Spot cell states, Grid initialization, material cache, neighbor map, numpy sync, backup/restore.

### test_pathfinding.py (9 tests)
A* pathfinding to exits, wall avoidance, blocked paths, dynamic replanning, neighbor counts.

### test_reset.py (13 tests)
Building construction, grid backup/restore, fuel reset regression, agent reset behavior.

### test_smoke.py (6 tests)
Smoke production from fire, Fick's law diffusion, barrier blocking, decay, bounds clamping.
