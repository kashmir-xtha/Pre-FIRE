"""Test agent pathfinding logic."""
import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent import Agent
from core.grid import Grid
from core.spot import Spot
from utils.utilities import state_value


class TestAgentPathfinding:
    """Test agent pathfinding and navigation."""
    
    @pytest.fixture
    def basic_grid(self):
        """Create simple test grid (20x20, no obstacles)."""
        grid = Grid(rows=20, width=800, floor=0)
        # Add an exit at bottom-right
        exit_spot = grid.grid[19][19]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        return grid, exit_spot
    
    def test_agent_finds_exit(self, basic_grid):
        """Agent should find path to exit."""
        grid, exit_spot = basic_grid
        start_spot = grid.grid[5][5]
        
        agent = Agent(grid, start_spot, floor=0, building=None)
        path = agent.best_path()
        
        assert len(path) > 0, "Should find a path"
        assert path[-1] == exit_spot, "Path should end at exit"
        
        # Verify path is continuous (neighbors are adjacent)
        for i in range(len(path) - 1):
            curr = path[i]
            next_spot = path[i + 1]
            distance = max(abs(curr.row - next_spot.row), 
                          abs(curr.col - next_spot.col))
            assert distance <= 1, f"Path has gap at step {i}"
    
    def test_agent_avoids_walls(self):
        """Agent should navigate around walls."""
        grid = Grid(rows=20, width=800, floor=0)
        
        # Create wall barrier at row 10 (columns 5-14)
        for col in range(5, 15):
            grid.grid[10][col].make_barrier()
        
        # Add exit beyond wall
        exit_spot = grid.grid[15][10]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        
        # Rebuild material cache after modifying grid
        grid.ensure_material_cache()
        
        agent = Agent(grid, grid.grid[5][10], floor=0)
        path = agent.best_path()
        
        assert len(path) > 0, "Should find path around wall"
        
        # Verify no path cells are barriers
        for spot in path:
            assert not spot.is_barrier(), f"Path goes through barrier at {spot.row},{spot.col}"
    
    def test_no_path_when_surrounded(self):
        """Agent with no escape should return empty path."""
        grid = Grid(rows=10, width=400, floor=0)
        agent_pos = grid.grid[5][5]
        
        # Add an exit first (far away)
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        
        # Surround agent with fire (but not the agent's cell)
        for row in range(4, 7):
            for col in range(4, 7):
                if (row, col) != (5, 5):
                    grid.grid[row][col].make_barrier()
        
        # Rebuild material cache
        grid.ensure_material_cache()
        
        agent = Agent(grid, agent_pos, floor=0)
        path = agent.best_path()
        
        assert len(path) == 0, "Should return empty path if no escape"
    
    def test_path_updates_when_obstacles_appear(self):
        """Path should be recalculated when environment changes."""
        grid = Grid(rows=15, width=600, floor=0)
        
        # Add exit on right side
        exit_spot = grid.grid[7][14]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        
        agent = Agent(grid, grid.grid[7][1], floor=0)
        
        # First path - should be straight line
        path1 = agent.best_path()
        assert len(path1) > 0, "Should find initial path"
        
        # Block the direct route with fire
        for col in range(5, 10):
            grid.grid[7][col].make_barrier()
        
        grid.ensure_material_cache()
        
        # Force recompute path
        agent.path = []
        path2 = agent.best_path()
        
        # Should find alternate route
        assert len(path2) > 0, "Should find alternate path"
        assert path2 != path1, "New path should be different"
        
        # New path should avoid barriers
        for spot in path2:
            assert not spot.is_barrier(), "New path should avoid fire"


class TestGridNavigation:
    """Test grid navigation utilities."""
    
    def test_get_neighbors_exists(self):
        """Grid should provide neighbor information."""
        grid = Grid(rows=10, width=400, floor=0)
        center = grid.grid[5][5]
        
        # Check that neighbor_map exists and has entries
        neighbors = grid.neighbor_map[5][5]
        
        # Center cell should have 8 neighbors
        assert len(neighbors) == 8, "Center should have 8 neighbors in precomputed map"
        assert all(n is not None for n in neighbors)
    
    def test_corner_has_fewer_neighbors(self):
        """Corner cells should have fewer neighbors."""
        grid = Grid(rows=10, width=400, floor=0)
        
        # Top-left corner
        neighbors = grid.neighbor_map[0][0]
        
        # Corner should have exactly 3 neighbors
        assert len(neighbors) == 3, "Corner should have 3 neighbors"
    
    def test_edge_cells(self):
        """Edge cells should have appropriate number of neighbors."""
        grid = Grid(rows=10, width=400, floor=0)
        
        # Top edge (not corner)
        neighbors = grid.neighbor_map[0][5]
        
        # Top edge should have 5 neighbors
        assert len(neighbors) == 5, "Top edge should have 5 neighbors"


class TestAgentState:
    """Test agent state transitions."""
    
    def test_agent_starts_idle(self):
        """New agent should start in IDLE state."""
        grid = Grid(rows=10, width=400, floor=0)
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        
        agent = Agent(grid, grid.grid[2][2], floor=0)
        
        assert agent.state == "IDLE", "Agent should start in IDLE state"
        assert agent.health == 100, "Agent should start with full health"
        assert agent.alive is True, "Agent should start alive"
    
    def test_agent_detects_smoke(self):
        """Agent should detect smoke in environment."""
        grid = Grid(rows=10, width=400, floor=0)
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        
        agent = Agent(grid, grid.grid[5][5], floor=0)
        
        # Simulate smoke detection
        agent.known_smoke[5, 5] = 0.8  # High smoke level
        
        # Agent should detect smoke when checking
        has_smoke = np.any(agent.known_smoke > 0.5)
        assert bool(has_smoke), "Agent should detect smoke above threshold"


# Run tests with: pytest tests/test_pathfinding.py -v
