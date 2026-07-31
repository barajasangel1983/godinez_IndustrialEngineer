"""
Godínez IndustrialEngineer — CLI Entry Point

Usage:
    python main.py analyze "What's our OEE?"               # Run query
    python main.py report --session <id>                    # Generate report
    python main.py data --list                              # List datasets
    python main.py data --file production.csv --type production  # Import data
    python main.py config --show                            # Show config
    python main.py config set oee_thresholds.critical 60    # Set threshold
    python main.py config set database.url postgresql://... # Change database
    python main.py server                                   # Start API server

Run with --help for full usage information.
"""

import sys
import os

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.main import main

if __name__ == "__main__":
    main()
