"""
Godínez IndustrialEngineer — State definition

Pydantic state that flows through the LangGraph workflow.
Starts minimal (Phase 0) and grows with each phase.
"""

from typing import TypedDict, Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState


# ── Phase 4 Result Models ───────────────────────────────────────────────────────

class BottleneckFinding(BaseModel):
    """A single bottleneck finding with severity and recommendation."""
    station: str
    metric_name: str
    value: float
    unit: str
    severity: str  # "critical" | "high" | "medium" | "low"
    score: float  # 0-100 ranking score
    recommendation: str


class BottleneckResult(BaseModel):
    """Structured result from bottleneck detection analysis."""
    line_name: str = ""
    overall_severity: str = "low"  # "critical" | "high" | "medium" | "low"
    balance_delay_pct: float = 0.0
    theoretical_balance_efficiency_pct: float = 0.0
    constraint_station: str = ""
    constraint_utilization_pct: float = 0.0
    top_findings: List[BottleneckFinding] = []
    suggestions: List[str] = []
    data_points: int = 0

    def to_dict(self) -> dict:
        return {
            "line_name": self.line_name,
            "overall_severity": self.overall_severity,
            "balance_delay_pct": round(self.balance_delay_pct, 2),
            "theoretical_balance_efficiency_pct": round(self.theoretical_balance_efficiency_pct, 2),
            "constraint_station": self.constraint_station,
            "constraint_utilization_pct": round(self.constraint_utilization_pct, 2),
            "top_findings": [f.model_dump() for f in self.top_findings],
            "suggestions": self.suggestions,
            "data_points": self.data_points,
        }


class CostBreakdown(BaseModel):
    """A single cost category breakdown."""
    category: str
    amount: float
    unit: str  # e.g., "scrap_count", "hours", "defects"
    rate: float  # cost per unit
    total: float  # category_amount * rate

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "amount": round(self.amount, 2),
            "unit": self.unit,
            "rate": round(self.rate, 2),
            "total": round(self.total, 2),
        }


class CostResult(BaseModel):
    """Structured result from cost estimation analysis."""
    total_waste_cost: float = 0.0
    breakdown: List[CostBreakdown] = []
    waste_pareto: List[CostBreakdown] = []  # sorted by $ impact, descending
    roi_projections: List[dict] = []  # {suggestion, annual_savings, payback_months}
    data_points: int = 0

    def to_dict(self) -> dict:
        return {
            "total_waste_cost": round(self.total_waste_cost, 2),
            "breakdown": [b.to_dict() for b in self.breakdown],
            "waste_pareto": [b.to_dict() for b in self.waste_pareto],
            "roi_projections": self.roi_projections,
            "data_points": self.data_points,
        }


class GodinezState(MessagesState):
    """State schema for Godínez IndustrialEngineer."""

    # ── Input ──────────────────────────────────────────────
    query: str                          # Raw natural language input
    user_id: Optional[str] = None       # Optional session/user ID
    timestamp: Optional[str] = None     # When the query was received

    # ── Classification ─────────────────────────────────────
    intent: Optional[str] = None        # Classified intent (e.g. "oee", "bottleneck", "trend")
    confidence: Optional[float] = None  # Classification confidence (0-1)
    entities: dict = {}                 # Detected entities (machines, dates, shifts)
    human_review: bool = False          # Flag for low-confidence classifications

    # ── Analysis Results ───────────────────────────────────
    # Each phase adds its result type here.
    # Phase 1: oee_analysis: Optional[dict]
    # Phase 3: trend_analysis: Optional[dict]
    # Phase 4: bottleneck_result: Optional[BottleneckResult], cost_result: Optional[CostResult]

    # ── Output ─────────────────────────────────────────────
    response: Optional[str] = None      # Final text response
    report: Optional[str] = None        # Markdown report content
    attachments: Optional[List[str]] = None  # File paths (charts, PDFs, etc.)

    # ── Errors & Metadata ─────────────────────────────────
    errors: List[str] = []              # Accumulated errors during execution
    metadata: dict = {}                 # Arbitrary metadata (latency, token usage, etc.)
