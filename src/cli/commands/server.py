"""
Godínez IndustrialEngineer — CLI server command

Usage:
    python main.py server                    # Start API server
    python main.py server --host 0.0.0.0     # Bind to all interfaces
    python main.py server --port 8000        # Custom port
"""

import sys
import os


def server(args):
    """Start the FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn is not installed.")
        print("   Install it with: pip install uvicorn")
        sys.exit(1)

    host = args.host or "0.0.0.0"
    port = args.port or 8000
    reload = args.reload

    print()
    print("=" * 70)
    print("  Godínez IndustrialEngineer — API Server")
    print("=" * 70)
    print(f"  Host:    {host}")
    print(f"  Port:    {port}")
    print(f"  Reload:  {'enabled' if reload else 'disabled'}")
    print("=" * 70)
    print()
    print("  ⚠️  Press Ctrl+C to stop the server.")
    print("  📚 API docs:     http://localhost:{port}/docs".format(port=port))
    print("  🏥 Health check: http://localhost:{port}/health".format(port=port))
    print()

    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )
