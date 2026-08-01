"""
Godínez IndustrialEngineer — CLI analyze command

Usage:
    python main.py analyze "What's our OEE today?"
    python main.py analyze "Show me bottleneck analysis" --session my-session
"""

import sys
import os
import uuid
from datetime import datetime, timezone

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from src.graph import build_workflow
from src.graph.session_datasets import get_active_dataset
from src.persistence import is_persistence_available
from src.persistence.repositories import persist_query_result
from src.config import DATA_DIR


def analyze(args):
    """Run a query through the workflow and display results."""
    query = args.query
    session_id = args.session or str(uuid.uuid4())
    enable_tracing = args.trace

    # Build and compile the workflow with observability
    workflow, obs_context = build_workflow(
        session_id=session_id,
        enable_tracing=enable_tracing,
    )
    compiled = workflow.compile()

    # Initial state with the query
    initial_state = {
        "query": query,
        "messages": [{"role": "user", "content": query}],
        "session_id": session_id,
    }
    active_dataset = get_active_dataset(session_id)
    if active_dataset:
        initial_state["csv_path"] = str(DATA_DIR / active_dataset)

    # Run the workflow
    result = compiled.invoke(initial_state)

    # Extract metrics and metadata
    summary = obs_context["metrics"].get_summary()
    metadata = result.get("metadata", {})
    intent = result.get("intent") or metadata.get("intent", "unknown")
    confidence = metadata.get("classification_confidence")

    # Build response display
    response = result.get("response", "No response generated.")

    # Persist to DB if available
    if is_persistence_available():
        try:
            persist_query_result(
                session_id=session_id,
                query_text=query,
                intent=intent,
                confidence=confidence,
                response=response,
                metadata=metadata,
                charts=result.get("charts"),
            )
        except Exception:
            # Persistence is best-effort — don't crash the CLI if DB fails
            pass

    # Header
    print()
    print("=" * 70)
    print("  Godínez IndustrialEngineer — Analysis")
    print("=" * 70)
    print(f"  Session:   {session_id}")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Trace:     {'enabled' if enable_tracing else 'disabled'}")
    print("=" * 70)
    print()

    # Intent badge
    print(f"  Intent: {intent}")
    print(f"  Confidence: {metadata.get('classification_confidence', 0):.1%}" if metadata.get("classification_confidence") else "  Confidence: N/A")
    print()
    print("-" * 70)

    # Response body
    if result.get("charts"):
        # Print response text
        print(response)
        print()
        print("-" * 70)
        # List chart attachments
        print(f"\n  📊 Charts generated: {len(result['charts'])}")
        for i, chart in enumerate(result["charts"], 1):
            filename = chart.get("filename", f"chart_{i}.png")
            print(f"    {i}. {filename} (base64 embedded)")
    else:
        print(response)

    print()
    print("-" * 70)

    # Execution summary
    nodes = summary.get("execution_order", [])
    latency = summary.get("total_latency_ms", 0)
    tokens = summary.get("tokens_used", 0)

    print()
    if nodes:
        print(f"  📊 Execution: {len(nodes)} nodes in {latency:.1f}ms")
        if tokens:
            print(f"  🔤 Tokens used: {tokens}")
        print(f"  🔄 Flow: {' → '.join(nodes)}")
    print()
    print("=" * 70)

    # Return for programmatic use (testing)
    return {
        "session_id": session_id,
        "query": query,
        "intent": intent,
        "response": response,
        "metadata": metadata,
        "execution_summary": summary,
        "charts": result.get("charts"),
    }
