"""
Leader Agent State Schema — Defines the state structure for the LangGraph orchestrator.
"""

from typing import Dict, Any, List, Optional, TypedDict

class LeaderAgentState(TypedDict):
    # Input
    raw_payload: Dict[str, Any]
    job_id: int
    user_id: Optional[str]
    
    # Context
    context: Dict[str, Any]
    
    # Intermediate results
    worker_type: str
    ai_metadata: Dict[str, Any]
    draft_variants: Dict[str, Any] # { "original": {...}, "viral_optimized": {...} }
    
    # Loop control
    pacing_errors: List[str]
    attempts: int
    
    # Final Result
    final_job_id: Optional[int]
