"""
OEE Calculator — Deterministic math for Overall Equipment Effectiveness

OEE = Availability × Performance × Quality
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class OEEResult:
    """Complete OEE analysis result."""
    
    # Core metrics
    availability: float  # percentage (0-100)
    performance: float   # percentage (0-100)
    quality: float       # percentage (0-100)
    oee: float           # final OEE score (0-100)
    
    # Component details
    planned_production_time: float  # minutes
    actual_run_time: float          # minutes
    downtime: float                 # minutes
    ideal_cycle_time: float         # seconds per unit
    total_count: int                # total units produced
    good_count: int                 # good units
    defect_count: int = 0         # defective units
    
    # Historical trend
    trend: list[dict] = None  # list of daily OEE points
    
    # Classification
    rating: str = ""          # "critical", "needs_improvement", "good", "world_class"
    recommendation: str = ""  # actionable recommendation
    
    def __post_init__(self):
        """Calculate derived values and classification."""
        if self.trend is None:
            self.trend = []
        
        self.defect_count = self.total_count - self.good_count
        self.rating = self._classify()
        self.recommendation = self._generate_recommendation()
    
    def _classify(self) -> str:
        """Classify OEE score based on industry benchmarks."""
        if self.oee >= 90.0:
            return "world_class"
        elif self.oee >= 85.0:
            return "good"
        elif self.oee >= 75.0:
            return "needs_improvement"
        else:
            return "critical"
    
    def _generate_recommendation(self) -> str:
        """Generate recommendation based on lowest component."""
        components = {
            "availability": self.availability,
            "performance": self.performance,
            "quality": self.quality,
        }
        
        lowest_component = min(components, key=components.get)
        
        recommendations = {
            "availability": (
                "Focus on reducing downtime. Review breakdown frequency and duration. "
                "Implement preventive maintenance schedules and backup equipment strategies."
            ),
            "performance": (
                "Focus on speed losses. Investigate minor stoppages and reduced run rates. "
                "Consider equipment tuning and operator training to achieve ideal cycle times."
            ),
            "quality": (
                "Focus on defects and rework. Review quality control processes and material "
                "consistency. Implement root cause analysis for top defect categories."
            ),
        }
        
        return recommendations.get(lowest_component, "Review overall OEE performance.")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "oee_score": self.oee,
            "availability": self.availability,
            "performance": self.performance,
            "quality": self.quality,
            "total_count": self.total_count,
            "good_count": self.good_count,
            "defect_count": self.defect_count,
            "rating": self.rating,
            "recommendation": self.recommendation,
            "trend_points": len(self.trend),
        }


def calculate_oee(
    planned_minutes: float,
    actual_run_minutes: float,
    downtime_minutes: float,
    ideal_cycle_time_seconds: float,
    total_count: int,
    good_count: int,
) -> OEEResult:
    """
    Calculate OEE for a single production period.
    
    Args:
        planned_minutes: Planned production time (minutes)
        actual_run_minutes: Actual run time (minutes)
        downtime_minutes: Unplanned downtime (minutes)
        ideal_cycle_time_seconds: Theoretical ideal cycle time (seconds)
        total_count: Total units produced
        good_count: Good quality units produced
    
    Returns:
        OEEResult with all metrics calculated
    """
    
    # Availability = Run Time / Planned Production Time
    if planned_minutes > 0:
        availability = (actual_run_minutes / planned_minutes) * 100
    else:
        availability = 0.0
    
    # Performance = (Ideal Cycle Time × Total Count) / Run Time
    # Note: Convert ideal cycle time to minutes for consistency
    if actual_run_minutes > 0:
        performance = (
            (ideal_cycle_time_seconds * total_count / 60) / actual_run_minutes
        ) * 100
        # Cap at 100% (can't be faster than ideal)
        performance = min(performance, 100.0)
    else:
        performance = 0.0
    
    # Quality = Good Count / Total Count
    if total_count > 0:
        quality = (good_count / total_count) * 100
    else:
        quality = 0.0
    
    # OEE = Availability × Performance × Quality
    oee = (availability / 100) * (performance / 100) * (quality / 100) * 100
    
    return OEEResult(
        availability=round(availability, 2),
        performance=round(performance, 2),
        quality=round(quality, 2),
        oee=round(oee, 2),
        planned_production_time=planned_minutes,
        actual_run_time=actual_run_minutes,
        downtime=downtime_minutes,
        ideal_cycle_time=ideal_cycle_time_seconds,
        total_count=total_count,
        good_count=good_count,
    )


def calculate_average_oee(results: list[OEEResult]) -> OEEResult:
    """
    Calculate average OEE across multiple production periods.
    
    Args:
        results: List of OEEResult objects
    
    Returns:
        OEEResult with average metrics
    """
    if not results:
        return OEEResult(
            availability=0, performance=0, quality=0, oee=0,
            planned_production_time=0, actual_run_time=0, downtime=0,
            ideal_cycle_time=0, total_count=0, good_count=0,
        )
    
    avg_availability = sum(r.availability for r in results) / len(results)
    avg_performance = sum(r.performance for r in results) / len(results)
    avg_quality = sum(r.quality for r in results) / len(results)
    
    # Calculate weighted OEE from aggregated totals
    total_planned = sum(r.planned_production_time for r in results)
    total_run = sum(r.actual_run_time for r in results)
    total_downtime = sum(r.downtime for r in results)
    total_count = sum(r.total_count for r in results)
    total_good = sum(r.good_count for r in results)
    
    return calculate_oee(
        planned_minutes=total_planned,
        actual_run_minutes=total_run,
        downtime_minutes=total_downtime,
        ideal_cycle_time_seconds=results[0].ideal_cycle_time,  # Assume same ideal cycle time
        total_count=total_count,
        good_count=total_good,
    )
