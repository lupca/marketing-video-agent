"""
Leader Graph — LangGraph implementation for the Leader Agent workflow.
Modular composition entry point.
"""

import logging
from typing import Literal

from langgraph.graph import StateGraph, START, END

from worker_leader.state import LeaderAgentState
from worker_leader.nodes import (
    extract_context_node,
    routing_node,
    draft_generator_node,
    pacing_validator_node,
    healing_node,
    persistence_node
)

logger = logging.getLogger(__name__)

# ── Conditional Edges ─────────────────────────────────────────────────────────

def pacing_condition(state: LeaderAgentState) -> Literal["refinement", "healing"]:
    """Determines whether to retry LLM generation or proceed to healing."""
    if not state["pacing_errors"]:
        return "healing"
    
    if state["attempts"] >= 3:
        logger.warning("Max pacing attempts reached. Proceeding to healing with existing errors.")
        return "healing"
        
    return "refinement"

# ── Graph Construction ───────────────────────────────────────────────────────

def create_leader_graph():
    workflow = StateGraph(LeaderAgentState)
    
    # Add Nodes
    workflow.add_node("extract", extract_context_node)
    workflow.add_node("router", routing_node)
    workflow.add_node("generator", draft_generator_node)
    workflow.add_node("validator", pacing_validator_node)
    workflow.add_node("healing", healing_node)
    workflow.add_node("persistence", persistence_node)
    
    # Define Edges
    workflow.add_edge(START, "extract")
    workflow.add_edge("extract", "router")
    workflow.add_edge("router", "generator")
    workflow.add_edge("generator", "validator")
    
    # Loop Control
    workflow.add_conditional_edges(
        "validator",
        pacing_condition,
        {
            "refinement": "generator",
            "healing": "healing"
        }
    )
    
    workflow.add_edge("healing", "persistence")
    workflow.add_edge("persistence", END)
    
    return workflow.compile()

# Singleton compiled instance for external callers
leader_graph = create_leader_graph()
