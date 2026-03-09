"""
Verification script to test backward compatibility after refactoring.
Run this to ensure all imports work correctly.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all imports work correctly."""
    errors = []
    success = []
    
    # Test 1: Original Agent import (backward compatibility)
    try:
        from core.agent import Agent
        success.append("✓ Original Agent import works (backward compatible)")
    except Exception as e:
        errors.append(f"✗ Original Agent import failed: {e}")
    
    # Test 2: Agent submodules
    try:
        from core.agent import AgentVision, AgentPathplanner, AgentMovement
        success.append("✓ Agent submodules import works")
    except Exception as e:
        errors.append(f"✗ Agent submodules import failed: {e}")
    
    # Test 3: Individual submodule imports
    try:
        from core.agent.agent_vision import AgentVision
        from core.agent.agent_pathplanner import AgentPathplanner
        from core.agent.agent_movement import AgentMovement, AgentState
        success.append("✓ Individual submodule imports work")
    except Exception as e:
        errors.append(f"✗ Individual submodule imports failed: {e}")
    
    # Test 4: Core imports (Grid, Spot, etc.)
    try:
        from core.grid import Grid
        from core.spot import Spot
        from core.simulation import Simulation
        success.append("✓ Core module imports work")
    except Exception as e:
        errors.append(f"✗ Core module imports failed: {e}")
    
    # Print results
    print("=" * 60)
    print("IMPORT VERIFICATION RESULTS")
    print("=" * 60)
    print()
    
    if success:
        print("PASSED TESTS:")
        for msg in success:
            print(f"  {msg}")
        print()
    
    if errors:
        print("FAILED TESTS:")
        for msg in errors:
            print(f"  {msg}")
        print()
    
    # Summary
    total = len(success) + len(errors)
    print("=" * 60)
    print(f"SUMMARY: {len(success)}/{total} tests passed")
    print("=" * 60)
    
    if errors:
        print("\n⚠️  Some imports failed. Check errors above.")
        return False
    else:
        print("\n✓ All imports working! Backward compatibility maintained.")
        return True


def test_basic_functionality():
    """Test basic functionality of key classes."""
    print("\n" + "=" * 60)
    print("BASIC FUNCTIONALITY TEST")
    print("=" * 60)
    print()
    
    try:
        # Test Agent class can be instantiated
        from core.grid import Grid
        from core.agent import Agent
        
        grid = Grid(rows=20, width=800, floor=0)
        spot = grid.grid[5][5]
        agent = Agent(grid, spot, floor=0)
        
        print("✓ Agent can be instantiated")
        print(f"  - Agent health: {agent.health}")
        print(f"  - Agent alive: {agent.alive}")
        print(f"  - Agent state: {agent.state}")
        
        return True
        
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    
    print("\n🔍 Testing Fire Evacuation Simulation Imports...\n")
    
    # Run import tests
    imports_ok = test_imports()
    
    # Run functionality tests
    if imports_ok:
        functionality_ok = test_basic_functionality()
    else:
        print("\n/|\\  Skipping functionality tests due to import failures.")
        functionality_ok = False
    
    # Exit with appropriate code
    if imports_ok and functionality_ok:
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED! System ready to use.")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ SOME TESTS FAILED. Please check errors above.")
        print("=" * 60)
        sys.exit(1)
