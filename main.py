"""
Godínez IndustrialEngineer — Main CLI entry point

Usage:
  python main.py "What's our OEE today?"
  python main.py --help

Phase 2: Observability integrated (metrics, logging, optional LangSmith tracing)
"""

import sys
import os

# Load .env for local secrets (API keys, etc.)
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.graph import build_workflow
from src.graph.state import GodinezState


def run_query(
    query: str,
    session_id: str = "",
    enable_tracing: bool = False,
) -> dict:
    """
    Run a single query through the workflow and return the response.

    Args:
        query: User's natural language query
        session_id: Optional session identifier for tracking
        enable_tracing: Whether to enable LangSmith tracing

    Returns:
        Dict with response, metadata, and execution summary
    """
    # Build and compile the workflow with observability
    workflow, obs_context = build_workflow(
        session_id=session_id,
        enable_tracing=enable_tracing,
    )
    app = workflow.compile()

    # Initial state with the query
    initial_state = {
        "query": query,
        "messages": [{"role": "user", "content": query}],
    }

    # Run the workflow
    result = app.invoke(initial_state)

    # Extract execution metrics
    summary = obs_context["metrics"].get_summary()

    return {
        "response": result.get("response", "No response generated."),
        "metadata": result.get("metadata", {}),
        "execution_summary": summary,
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Godínez IndustrialEngineer — AI-powered manufacturing analysis",
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Natural language query (e.g., \"What's our OEE today?\")",
    )
    parser.add_argument(
        "--session",
        help="Session ID for tracking/observability",
        default="",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Enable LangSmith tracing (requires LANGSMITH_API_KEY)",
    )

    args = parser.parse_args()

    if not args.query:
        print("Usage: python main.py \"<query>\"")
        print("\nExample: python main.py \"What's our OEE today?\"")
        print("\nOptions:")
        print("  --session ID   Session identifier for tracking")
        print("  --trace        Enable LangSmith tracing")
        sys.exit(1)

    print(f"\n🔍 Godínez IndustrialEngineer")
    print(f"   Query: {args.query}")
    print(f"   Session: {args.session or 'auto'}")
    print(f"   Trace: {'enabled' if args.trace else 'disabled'}")
    print(f"   {'=' * 60}")

    try:
        result = run_query(args.query, session_id=args.session, enable_tracing=args.trace)
        print(f"\n{result['response']}")

        # Print execution summary (compact)
        summary = result.get("execution_summary", {})
        if summary:
            nodes = summary.get("execution_order", [])
            latency = summary.get("total_latency_ms", 0)
            print(f"\n📊 Execution: {len(nodes)} nodes in {latency:.1f}ms")
            if nodes:
                print(f"   Flow: {' → '.join(nodes)}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
