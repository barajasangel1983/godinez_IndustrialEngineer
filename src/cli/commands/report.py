"""
Godínez IndustrialEngineer — CLI report command

Usage:
    python main.py report --session <session_id>
    python main.py report --session <session_id> --format json
    python main.py report --session <session_id> --file report.txt
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from src.persistence import is_persistence_available, get_db_session
from src.persistence.repositories import get_session_summary, get_results_by_session
from src.persistence.config import get_url


def report(args):
    """Generate a formatted report from a past session."""
    session_id = args.session

    if not is_persistence_available():
        print("❌ Persistence is not enabled.")
        print("   Set DATABASE_URL environment variable to enable.")
        print(f"   Current DATABASE_URL: {os.environ.get('DATABASE_URL', 'not set')}")
        sys.exit(1)

    db_session = get_db_session()
    if db_session is None:
        print("❌ Database connection failed.")
        sys.exit(1)

    # Check if session exists
    summary = get_session_summary(session_id)
    if summary["query_count"] == 0:
        print(f"❌ Session '{session_id}' not found.")
        print("   Available sessions:")
        from src.persistence.repositories import get_all_sessions
        from sqlalchemy import desc

        sessions = get_all_sessions()
        for s in sessions[:10]:
            print(f"   - {s.session_id}")
        db_session.close()
        sys.exit(1)

    # Get all queries for the session
    queries = get_results_by_session(session_id)
    db_session.close()

    # Build report
    report_format = args.format or "text"

    if report_format == "json":
        # JSON format — programmatic
        report_data = {
            "session_id": session_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "queries": [],
        }

        for q in queries:
            query_data = {
                "query_id": q.id,
                "query_text": q.query_text,
                "intent": q.intent,
                "confidence": q.confidence / 100 if q.confidence is not None else None,
                "timestamp": q.timestamp.isoformat() if q.timestamp else None,
                "response": q.result.response if q.result else None,
                "metadata": q.result.analysis_metadata if q.result else None,
                "charts": q.result.charts if q.result else None,
                "errors": q.result.errors if q.result else None,
            }
            report_data["queries"].append(query_data)

        if args.file:
            with open(args.file, "w") as f:
                json.dump(report_data, f, indent=2)
            print(f"✅ Report saved to {args.file}")
        else:
            print(json.dumps(report_data, indent=2))

    else:
        # Text format — human-readable
        print()
        print("=" * 70)
        print("  Godínez IndustrialEngineer — Session Report")
        print("=" * 70)
        print(f"  Session:    {session_id}")
        print(f"  Generated:  {datetime.now(timezone.utc).isoformat()}")
        print(f"  Queries:    {summary['query_count']}")
        print(f"  Intents:    {', '.join(summary['intents']) if summary['intents'] else 'N/A'}")
        if summary.get("first_query"):
            print(f"  First:      {summary['first_query'][:10]}")
        if summary.get("last_query"):
            print(f"  Last:       {summary['last_query'][:10]}")
        print("=" * 70)
        print()

        for i, q in enumerate(queries, 1):
            print(f"  Query #{i} [{q.timestamp.strftime('%Y-%m-%d %H:%M') if q.timestamp else 'unknown'}]")
            print(f"    Text:   {q.query_text}")
            print(f"    Intent: {q.intent or 'unknown'}")
            if q.confidence is not None:
                print(f"    Confidence: {q.confidence / 100:.1%}")
            if q.result:
                print(f"    Response:")
                for line in q.result.response.split("\n"):
                    print(f"      {line}")
                if q.result.charts:
                    print(f"    📊 Charts: {len(q.result.charts)}")
            print()
            if i < len(queries):
                print("-" * 70)
                print()

        print("=" * 70)
        print()

    # Return for programmatic use (testing)
    return {
        "session_id": session_id,
        "summary": summary,
        "queries": [
            {
                "id": q.id,
                "query_text": q.query_text,
                "intent": q.intent,
                "response": q.result.response if q.result else None,
            }
            for q in queries
        ],
    }
