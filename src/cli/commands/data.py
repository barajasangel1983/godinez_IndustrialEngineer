"""
Godínez IndustrialEngineer — CLI data command

Usage:
    python main.py data --list                              # List available datasets
    python main.py data --file production.csv --type production  # Import dataset
    python main.py data --file production.csv --type production --overwrite  # Overwrite existing
"""

import sys
import os
import csv
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from src.config import DATA_DIR
from src.tools.csv_reader import CsvReader


def data_list():
    """List all available datasets in the data directory."""
    if not DATA_DIR.exists():
        print("  ❌ Data directory not found:")
        print(f"     {DATA_DIR}")
        return

    datasets = list(DATA_DIR.glob("*.csv"))
    if not datasets:
        print("  📁 No datasets found.")
        print(f"     Data directory: {DATA_DIR}")
        print()
        print("  💡 Import a dataset:")
        print("     python main.py data --file production.csv --type production")
        return

    print(f"  📁 Datasets in {DATA_DIR}:")
    print()

    # Group by type
    production_files = [f for f in datasets if "production" in f.stem.lower()]
    other_files = [f for f in datasets if "production" not in f.stem.lower()]

    if production_files:
        print("  Production Data:")
        for f in sorted(production_files):
            size = f.stat().st_size
            modified = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"    • {f.name} ({size:,} bytes, modified {modified})")

        # Try to show record counts
        try:
            reader = CsvReader()
            for f in sorted(production_files):
                if f.exists():
                    records = reader.read_csv(str(f))
                    print(f"      └─ {len(records)} records, machines: {reader.get_machine_ids(records)}")
        except Exception:
            pass

    if other_files:
        print()
        print("  Other Data:")
        for f in sorted(other_files):
            size = f.stat().st_size
            modified = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"    • {f.name} ({size:,} bytes, modified {modified})")

    print()
    print(f"  Total: {len(datasets)} file(s)")


def data_import(args):
    """Import a dataset file."""
    file_path = args.file
    data_type = args.type or "production"
    overwrite = args.overwrite

    # Resolve file path
    if not os.path.isabs(file_path):
        # Try current directory first, then data directory
        if os.path.exists(file_path):
            file_path = os.path.abspath(file_path)
        else:
            data_dir_file = os.path.join(DATA_DIR, file_path)
            if os.path.exists(data_dir_file):
                file_path = data_dir_file
            else:
                print(f"❌ File not found: {file_path}")
                return

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    # Check if file already exists in data dir
    dest_path = DATA_DIR / os.path.basename(file_path)
    if dest_path.exists() and not overwrite:
        print(f"⚠️  {dest_path.name} already exists.")
        print(f"   Use --overwrite to replace it.")
        return

    # Validate CSV structure
    try:
        reader = CsvReader()
        records = reader.read_csv(file_path)
    except Exception as e:
        print(f"❌ Failed to read CSV: {e}")
        return

    # Type-specific validation
    if data_type == "production":
        required_cols = {"date", "shift", "machine_id", "planned_minutes", "actual_run_minutes",
                         "ideal_cycle_time_seconds", "total_count", "good_count"}
        actual_cols = set(records[0].keys()) if records else set()
        missing = required_cols - actual_cols
        if missing:
            print(f"❌ Production CSV missing required columns: {', '.join(sorted(missing))}")
            print(f"   Found columns: {', '.join(sorted(actual_cols))}")
            return

    # Copy file to data directory
    import shutil
    shutil.copy2(file_path, dest_path)

    # Summary
    print(f"✅ Dataset imported: {dest_path.name}")
    print(f"   Type:      {data_type}")
    print(f"   Records:   {len(records)}")
    if records:
        if "machine_id" in records[0]:
            machines = reader.get_machine_ids(records)
            print(f"   Machines:  {machines}")
        if "date" in records[0]:
            dates = reader.get_date_range(records)
            print(f"   Date range: {dates[0]} to {dates[1]}")

    print(f"   Location:  {dest_path}")


def data(args):
    """Handle data subcommand — list or import datasets."""
    if args.list:
        data_list()
    elif args.file:
        data_import(args)
    else:
        # Default: list datasets
        data_list()
