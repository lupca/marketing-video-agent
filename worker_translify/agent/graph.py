from langgraph.graph import StateGraph, END
from worker_translify.agent.state import TranslifyAgentState
from worker_translify.agent.nodes import (
    glossary_extractor_node,
    sliding_translation_node,
    reflective_adaptation_node,
    pacing_validator_node,
    trimming_agentic_node,
    fallback_healing_node
)

def route_after_validation(state: TranslifyAgentState) -> str:
    violations = state.get("pacing_violations", [])
    attempts = state.get("trimming_attempts", {})
    
    # Check if we have any violation that has been tried < 3 times
    has_viable_violation = False
    for v in violations:
        if attempts.get(v, 0) < 3:
            has_viable_violation = True
            break
            
    if has_viable_violation:
        return "trimming_agentic_node"
    else:
        return "fallback_healing_node"

# ── Construct the StateGraph ────────────────────────────────────────────────

workflow = StateGraph(TranslifyAgentState)

# 1. Register all nodes
workflow.add_node("glossary_extractor_node", glossary_extractor_node)
workflow.add_node("sliding_translation_node", sliding_translation_node)
workflow.add_node("reflective_adaptation_node", reflective_adaptation_node)
workflow.add_node("pacing_validator_node", pacing_validator_node)
workflow.add_node("trimming_agentic_node", trimming_agentic_node)
workflow.add_node("fallback_healing_node", fallback_healing_node)

# 2. Setup standard edges
workflow.set_entry_point("glossary_extractor_node")
workflow.add_edge("glossary_extractor_node", "sliding_translation_node")
workflow.add_edge("sliding_translation_node", "reflective_adaptation_node")
workflow.add_edge("reflective_adaptation_node", "pacing_validator_node")

# 3. Setup conditional routing edge based on validator checks
workflow.add_conditional_edges(
    "pacing_validator_node",
    route_after_validation,
    {
        "trimming_agentic_node": "trimming_agentic_node",
        "fallback_healing_node": "fallback_healing_node"
    }
)

# 4. Route back to pacing validator from trimming agent
workflow.add_edge("trimming_agentic_node", "pacing_validator_node")

# 5. Route fallback healer to END (removing persistence_node)
workflow.add_edge("fallback_healing_node", END)

# Compile graph app
app = workflow.compile()
