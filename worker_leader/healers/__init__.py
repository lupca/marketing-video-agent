"""
Defensive healers for normalizing AI-generated draft parameters.

Each healer ensures a specific worker type's draft_parameters dictionary
contains all required fields with sensible defaults, preventing downstream
worker crashes from incomplete LLM output.
"""

from worker_leader.healers.dispatcher import heal_draft_parameters

__all__ = ["heal_draft_parameters"]
