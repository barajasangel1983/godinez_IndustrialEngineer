"""
Godínez IndustrialEngineer — Workflow definition

Minimal LangGraph StateGraph for Phase 0.
Nodes: intake → router → analyze → response → END

This skeleton is designed so that each Phase adds nodes without breaking existing flow.
"""

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from .state import GodinezState
from .nodes.intake import intake_node
from .nodes.classify import classify_node
from .nodes.router import router_node
from .nodes.analyze import analyze_node
from .nodes.response import response_node


def build_workflow() -> StateGraph:
    """Build and return the compiled Godínez IndustrialEngineer workflow."""

    workflow = StateGraph(GodinezState)

    # ── Add nodes ────────────────────────────────────────
    workflow.add_node("intake", intake_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("router", router_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("response", response_node)

    # ── Edges ───────────────────────────────────────────
    workflow.add_edge("intake", "classify")
    workflow.add_edge("classify", "router")
    workflow.add_edge("router", "analyze")
    workflow.add_edge("analyze", "response")
    workflow.add_edge("response", END)

    # ── Entry point ─────────────────────────────────────
    workflow.set_entry_point("intake")

    return workflow
