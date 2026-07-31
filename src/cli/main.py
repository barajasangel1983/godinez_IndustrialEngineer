"""
Godínez IndustrialEngineer — CLI Entry Point

Usage:
    python main.py analyze "What's our OEE?"               # Run query
    python main.py report --session <id>                    # Generate report
    python main.py data --list                              # List datasets
    python main.py data --file production.csv --type production  # Import data
    python main.py config --show                            # Show config
    python main.py config set oee_thresholds.critical 60    # Set threshold
    python main.py server                                   # Start API server

Run with --help for full usage information.
"""

import sys
import os
import argparse

# Load .env for local secrets (API keys, etc.)
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def create_parser():
    """Create the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Godínez IndustrialEngineer — AI-powered manufacturing analysis",
        epilog="Use '<command> --help' for more information on a command.",
    )

    # ── Subparsers ──────────────────────────────────────────────
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=True,  # Force user to specify a command
    )

    # ── analyze ─────────────────────────────────────────────────
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run an analysis query",
        description="Run a natural language query through the manufacturing analysis agent.",
    )
    analyze_parser.add_argument(
        "query",
        help="Natural language query (e.g., \"What's our OEE today?\")",
    )
    analyze_parser.add_argument(
        "--session",
        help="Session ID for tracking/observability (auto-generated if not provided)",
        default="",
    )
    analyze_parser.add_argument(
        "--trace",
        action="store_true",
        help="Enable LangSmith tracing (requires LANGSMITH_API_KEY)",
    )

    # ── report ──────────────────────────────────────────────────
    report_parser = subparsers.add_parser(
        "report",
        help="Generate a formatted report from a past session",
        description="Retrieve and display a formatted report from a past analysis session.",
    )
    report_parser.add_argument(
        "--session",
        required=True,
        help="Session ID to generate report for",
    )
    report_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    report_parser.add_argument(
        "--file",
        help="Save report to file (default: print to stdout)",
    )

    # ── data ────────────────────────────────────────────────────
    data_parser = subparsers.add_parser(
        "data",
        help="Manage datasets",
        description="List or import production datasets.",
    )
    data_parser.add_argument(
        "--list",
        action="store_true",
        help="List available datasets in the data directory",
    )
    data_parser.add_argument(
        "--file",
        help="File path to import as a dataset",
    )
    data_parser.add_argument(
        "--type",
        choices=["production"],
        default="production",
        help="Dataset type (default: production)",
    )
    data_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing file with same name",
    )

    # ── config ──────────────────────────────────────────────────
    config_parser = subparsers.add_parser(
        "config",
        help="Show or edit configuration",
        description=(
            "View or modify application configuration.\n\n"
            "Examples:\n"
            "  python main.py config --show\n"
            "  python main.py config set oee_thresholds.critical 60\n"
            "  python main.py config set database.url postgresql://...\n"
        ),
    )
    config_parser.add_argument(
        "--show",
        action="store_true",
        help="Show current configuration (default if no action given)",
    )
    config_parser.add_argument(
        "config_args",
        nargs="*",
        metavar="ARG",
        help="'set KEY VALUE' to update a config value",
    )

    # ── server ──────────────────────────────────────────────────
    server_parser = subparsers.add_parser(
        "server",
        help="Start the API server",
        description="Start the FastAPI REST server for programmatic access.",
    )
    server_parser.add_argument(
        "--host",
        help="Host to bind to (default: 0.0.0.0)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        help="Port to bind to (default: 8000)",
    )
    server_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    return parser


def main():
    """Main CLI entry point with subcommand dispatch."""
    parser = create_parser()
    args = parser.parse_args()

    # Dispatch to the appropriate handler
    if args.command == "analyze":
        from src.cli.commands.analyze import analyze
        analyze(args)

    elif args.command == "report":
        from src.cli.commands.report import report
        report(args)

    elif args.command == "data":
        from src.cli.commands.data import data
        data(args)

    elif args.command == "config":
        from src.cli.commands.config import config
        config(args)

    elif args.command == "server":
        from src.cli.commands.server import server
        server(args)


if __name__ == "__main__":
    main()
