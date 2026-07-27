"""
Godínez IndustrialEngineer — Main CLI entry point

Usage:
  python main.py "What's our OEE today?"
  python main.py --help
"""

import sys
import os

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.graph import build_workflow
from src.graph.state import GodinezState


def run_query(query: str) -> str:
    """Run a single query through the workflow and return the response."""

    # Build and compile the workflow
    workflow = build_workflow()
    app = workflow.compile()

    # Initial state with the query
    initial_state = {
        "query": query,
        "messages": [{"role": "user", "content": query}],
    }

    # Run the workflow
    result = app.invoke(initial_state)

    # Extract and return the response
    return result.get("response", "No response generated.")


def main():
    """Main entry point."""

    if len(sys.argv) < 2:
        print("Usage: python main.py \"<query>\"")
        print("\nExample: python main.py \"What's our OEE today?\"")
        sys.exit(1)

    # Get the query from command line
    query = " ".join(sys.argv[1:])

    print(f"\n🔍 Godínez IndustrialEngineer")
    print(f"   Query: {query}")
    print(f"   {'=' * 60}")

    try:
        response = run_query(query)
        print(f"\n{response}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
