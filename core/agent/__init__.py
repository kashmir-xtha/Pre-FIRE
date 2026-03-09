"""
Agent package - contains the Agent class and its specialized submodules.

Submodules:
- AgentVision: Perception and environmental awareness
- AgentPathplanner: Pathfinding and route planning
- AgentMovement: Physical movement and damage handling
- AgentState: Behavioral state management (IDLE/REACTION/MOVING)

Usage:
    from core.agent import Agent
    from core.agent import AgentVision, AgentPathplanner, AgentMovement, AgentState
"""

from core.agent.agent import Agent, SparseFireGrid
from core.agent.agent_vision import AgentVision
from core.agent.agent_pathplanner import AgentPathplanner
from core.agent.agent_movement import AgentMovement, AgentState

__all__ = ['Agent', 'SparseFireGrid', 'AgentVision', 'AgentPathplanner', 'AgentMovement', 'AgentState']
