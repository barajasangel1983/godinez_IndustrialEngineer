"""
Synthetic Data Generator — Generate realistic production data for testing.

Creates CSV files with:
- Multi-line data (Lines 1-4)
- Built-in trends (improving/declining/stable)
- Seasonal patterns (day-of-week variations)
- Random anomalies (simulated breakdowns)
- Multiple shifts per day
- Realistic column ranges
"""

import csv
import random
import math
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


MACHINES = ["Line-1", "Line-2", "Line-3", "Line-4"]
SHIFTS = ["A", "B", "C"]
DOWNTIME_REASONS = [
    "breakdown", "setup", "material_shortage", "operator_break",
    "quality_check", "maintenance", "changeover", "power_outage"
]

BASE_PARAMS = {
    "Line-1": {"planned": 480, "ideal_cycle": 30, "base_oee": 0.88, "trend": 0.0005},
    "Line-2": {"planned": 480, "ideal_cycle": 35, "base_oee": 0.82, "trend": -0.0003},
    "Line-3": {"planned": 480, "ideal_cycle": 25, "base_oee": 0.91, "trend": 0.0001},
    "Line-4": {"planned": 480, "ideal_cycle": 40, "base_oee": 0.78, "trend": 0.0004},
}


def generate_synthetic_production(
    start_date: str = "2024-01-01",
    end_date: str = "2024-06-30",
    filepath: Optional[str | Path] = None,
    seed: int = 42,
) -> str:
    """
    Generate synthetic production CSV data.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        filepath: Output path (defaults to data/synthetic_production.csv)
        seed: Random seed for reproducibility

    Returns:
        Path to generated CSV
    """
    random.seed(seed)

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    rows = []
    current = start

    while current <= end:
        day_of_week = current.weekday()  # 0=Mon, 6=Sun
        day_num = (current - start).days

        # Skip weekends (lower utilization)
        weekend_factor = 0.85 if day_of_week >= 5 else 1.0

        for machine in MACHINES:
            params = BASE_PARAMS[machine]
            trend_factor = params["trend"] * day_num

            # Base OEE components with trend
            avail_base = 0.90 + trend_factor
            perf_base = 0.95 + trend_factor * 0.5
            qual_base = 0.97 + trend_factor * 0.3

            # Add day-of-week seasonality
            dow_season = math.sin(2 * math.pi * day_of_week / 5) * 0.02
            seasonality = 1.0 + dow_season * (1.0 if weekend_factor < 1 else 0.3)

            # Shift factor (shift C sometimes has fatigue)
            shift_hourly = 0.97 if SHIFTS.index("C") == 2 else 1.0

            # Apply randomness
            avail = (avail_base * seasonality * shift_hourly * weekend_factor +
                     random.gauss(0, 0.03))
            perf = min(1.0, perf_base * seasonality * shift_hourly + random.gauss(0, 0.02))
            qual = min(1.0, qual_base * seasonality * shift_hourly + random.gauss(0, 0.01))

            # Clamp to realistic ranges
            avail = max(0.60, min(0.99, avail))
            perf = max(0.70, min(1.00, perf))
            qual = max(0.80, min(1.00, qual))

            planned = params["planned"] * weekend_factor
            actual = planned * avail
            downtime = planned - actual

            # Ideal cycle time (fixed per machine, small variation)
            ideal_cycle = params["ideal_cycle"] * random.uniform(0.98, 1.02)

            # Production count
            potential_count = (actual * 60) / ideal_cycle
            total_count = int(potential_count * random.uniform(0.95, 1.05))
            good_count = int(total_count * qual * random.uniform(0.95, 1.02))
            good_count = min(good_count, total_count)

            # Downtime reason
            # Higher breakdown chance if availability is low
            if avail < 0.80:
                reason = random.choices(
                    DOWNTIME_REASONS,
                    weights=[25, 10, 10, 5, 10, 15, 10, 15],
                )[0]
            else:
                reason = random.choices(
                    DOWNTIME_REASONS,
                    weights=[5, 20, 15, 15, 10, 15, 10, 5],
                )[0]

            rows.append({
                "date": current.strftime("%Y-%m-%d"),
                "shift": random.choice(SHIFTS),
                "machine_id": machine,
                "planned_minutes": round(planned, 1),
                "actual_run_minutes": round(actual, 1),
                "downtime_minutes": round(downtime, 1),
                "ideal_cycle_time_seconds": round(ideal_cycle, 2),
                "total_count": total_count,
                "good_count": good_count,
                "downtime_reason": reason,
            })

        current += timedelta(days=1)

    # Write CSV
    out_path = filepath or Path(__file__).parent.parent.parent / "data" / "synthetic_production.csv"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "date", "shift", "machine_id", "planned_minutes",
        "actual_run_minutes", "downtime_minutes", "ideal_cycle_time_seconds",
        "total_count", "good_count", "downtime_reason"
    ]

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return str(out_path)


if __name__ == "__main__":
    path = generate_synthetic_production()
    print(f"✅ Generated synthetic data at: {path}")
