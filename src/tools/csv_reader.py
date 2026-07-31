"""
CSV Data Reader — Load and validate production log CSVs
"""

import csv
from pathlib import Path
from typing import Optional


def read_production_csv(filepath: str | Path) -> list[dict]:
    """
    Read and validate a production log CSV file.
    
    Args:
        filepath: Path to the CSV file
    
    Returns:
        List of dictionaries with production data
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If required columns are missing
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    
    required_columns = {
        "date", "shift", "machine_id", "planned_minutes",
        "actual_run_minutes", "downtime_minutes", "ideal_cycle_time_seconds",
        "total_count", "good_count", "downtime_reason"
    }
    
    rows = []
    
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        
        # Validate columns
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no headers")
        
        missing_columns = required_columns - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        
        for row in reader:
            # Convert numeric fields
            try:
                converted = {
                    "date": row["date"],
                    "shift": row["shift"],
                    "machine_id": row["machine_id"],
                    "planned_minutes": float(row["planned_minutes"]),
                    "actual_run_minutes": float(row["actual_run_minutes"]),
                    "downtime_minutes": float(row["downtime_minutes"]),
                    "ideal_cycle_time_seconds": float(row["ideal_cycle_time_seconds"]),
                    "total_count": int(row["total_count"]),
                    "good_count": int(row["good_count"]),
                    "downtime_reason": row.get("downtime_reason", "unknown"),
                }
                rows.append(converted)
            except (ValueError, KeyError) as e:
                # Skip malformed rows but log warning
                print(f"⚠️ Skipping malformed row: {row} — {e}")
    
    if not rows:
        raise ValueError("No valid data rows found in CSV")
    
    return rows


def get_machine_ids(rows: list[dict]) -> list[str]:
    """Extract unique machine IDs from production data."""
    return sorted(set(row["machine_id"] for row in rows))


def get_date_range(rows: list[dict]) -> tuple[str, str]:
    """Extract date range from production data."""
    dates = [row["date"] for row in rows]
    return min(dates), max(dates)


def filter_by_date(rows: list[dict], start_date: str, end_date: str) -> list[dict]:
    """Filter production data by date range."""
    return [
        row for row in rows
        if start_date <= row["date"] <= end_date
    ]


def filter_by_machine(rows: list[dict], machine_id: str) -> list[dict]:
    """Filter production data by machine."""
    return [
        row for row in rows
        if row["machine_id"] == machine_id
    ]


class CsvReader:
    """Object-oriented wrapper around csv_reader functions for backwards compat."""

    def __init__(self):
        pass

    def read_csv(self, filepath: str) -> list[dict]:
        return read_production_csv(filepath)

    @staticmethod
    def get_machine_ids(rows: list[dict]) -> list[str]:
        return get_machine_ids(rows)

    @staticmethod
    def get_date_range(rows: list[dict]) -> tuple[str, str]:
        return get_date_range(rows)

    @staticmethod
    def filter_by_date(rows: list[dict], start: str, end: str) -> list[dict]:
        return filter_by_date(rows, start, end)

    @staticmethod
    def filter_by_machine(rows: list[dict], machine_id: str) -> list[dict]:
        return filter_by_machine(rows, machine_id)
