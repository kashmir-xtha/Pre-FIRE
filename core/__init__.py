"""
core.agent package.

Exposes Agent at the package level so both import styles work:
    from core.agent import Agent          # old monolith style
    from core.agent.agent import Agent    # new submodule style
"""

from core.agent.agent import Agent, SparseFireGrid
from core.agent.agent_movement import AgentMovement, AgentState
from core.agent.agent_vision import AgentVision
from core.agent.agent_pathplanner import AgentPathplanner

__all__ = [
    "Agent",
    "SparseFireGrid",
    "AgentMovement",
    "AgentState",
    "AgentVision",
    "AgentPathplanner",
]