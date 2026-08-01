"""
Analysis node — Orchestrator that dispatches to intent-specific analysis nodes.

Phase 1: Single analysis (OEE only).
Phase 2+: Multi-tool chaining — supports multiple analysis types in one query.

Dispatches to ANALYSIS_HANDLERS based on intent.
If multiple intents are detected (via entities or intent list), chains them.
"""

from ..state import GodinezState
from . import oee_analysis
from . import bottleneck
from . import cost_analysis
from . import trend_analysis
from . import load_dataset

# Phase 1+ analysis capabilities
ANALYSIS_HANDLERS = {
    "oee": oee_analysis.oee_analysis_node,
    "bottleneck": bottleneck.bottleneck_node,
    "cost": cost_analysis.cost_node,
    "trend": trend_analysis.trend_analysis_node,
    "load_dataset": load_dataset.load_dataset_node,
}


def analyze_node(state: GodinezState) -> GodinezState:
    """
    Execute analysis based on intent. Supports:
    - Single intent: calls one handler
    - Multi-intent: chains multiple handlers (Phase 2+)
    
    Accumulates results in state.analysis_results dict.
    """
    intent = state.get("intent") or "general"
    errors = state.get("errors", [])
    
    # Start collecting results
    analysis_results = dict(state.get("analysis_results", {}))
    responses = []
    handler_metadata = {}

    # ── Single intent handler ──────────────────────────────
    handler = ANALYSIS_HANDLERS.get(intent)
    
    if handler:
        try:
            result = handler(state)
            
            # Extract metadata from handler result
            if "metadata" in result:
                handler_metadata = dict(result["metadata"])
                # Store in analysis_results under intent key
                analysis_results[intent] = handler_metadata
            
            if "response" in result:
                responses.append(result["response"])
            
            if result.get("errors"):
                errors.extend(result["errors"])
                
        except Exception as e:
            errors.append(f"Analysis '{intent}' failed: {e}")
            responses.append(f"⚠️ Analysis '{intent}' encountered an error: {e}")
    else:
        # Intent not implemented
        responses.append(
            f"Analysis for intent='{intent}' not yet implemented.\n\n"
            f"Query: {state.get('query', '')}\n\n"
            f"Implemented intents: {', '.join(ANALYSIS_HANDLERS.keys())}"
        )

    # ── Build final response ───────────────────────────────
    if not responses:
        responses.append("No analysis results available.")
    
    response = "\n\n".join(responses)
    
    return {
        **state,
        "response": response,
        "analysis_results": analysis_results,
        "errors": errors,
        "metadata": {
            **state.get("metadata", {}),
            **handler_metadata,  # Merge handler metadata
            "analyzed_intents": [intent],
            "analysis_result_count": len(analysis_results),
        },
    }
