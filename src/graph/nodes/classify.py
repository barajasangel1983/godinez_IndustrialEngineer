"""
Intent Classifier Node — LLM-based intent classification with entity extraction.

Phase 2: Replaces simple keyword matching with LLM-powered classification.
Returns: intent, confidence, extracted_entities, human_review flag

Fallback chain:
  1. Qwen3.6-35B-A3B via vLLM on DGX
  2. qwen3:8b via ollama on local machine (localhost:11434)
  3. Keyword matching fallback

Sets human_review=True when confidence < 0.5 (low-confidence threshold).
"""

import os
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from ..state import GodinezState

# ── Valid intents ─────────────────────────────────────────
VALID_INTENTS = [
    "oee",
    "bottleneck",
    "trend",
    "cost",
    "safety",
    "time_study",
    "general",
]

# ── Thresholds ────────────────────────────────────────────
LOW_CONFIDENCE_THRESHOLD = 0.5  # Flag for human review


@dataclass
class ClassificationResult:
    intent: str
    confidence: float
    entities: dict


def _get_llm_primary() -> ChatOpenAI:
    """Primary LLM: Qwen3.6-35B-A3B via vLLM on DGX."""
    dgx_url = os.environ.get("DGX_VLLM_URL", "http://100.74.225.3:8001/v1")
    return ChatOpenAI(
        model="Qwen/Qwen3.6-35B-A3B",
        base_url=dgx_url,
        api_key="none",
        temperature=0.0,
        request_timeout=60,
    )


def _get_llm_ollama() -> ChatOllama:
    """Local Ollama fallback: qwen3:8b."""
    return ChatOllama(
        model="qwen3:8b",
        base_url="http://localhost:11434",
        temperature=0.0,
        num_ctx=4096,
        request_timeout=5,  # 5 second timeout
    )


SYSTEM_PROMPT = """\
You are a manufacturing operations assistant classifier. Given a user query, identify the intent and extract relevant entities.

Available intents: {intents}
Respond in JSON format ONLY (no markdown, no explanations):
{{
  "intent": "<one of the available intents>",
  "confidence": <float between 0 and 1>,
  "entities": {{
    "machines": ["<machine IDs if mentioned, else empty>"],
    "dates": ["<date ranges if mentioned, else empty>"],
    "shifts": ["<shift IDs if mentioned, else empty>"]
  }}
}}

User query: {query}\
"""


def classify_node(state: GodinezState) -> GodinezState:
    """
    Classify intent using LLM with confidence scoring and entity extraction.

    Fallback chain:
      1. Qwen3.6-35B-A3B via vLLM on DGX (configurable via DGX_VLLM_URL env var)
      2. qwen3:8b via ollama on local machine (localhost:11434)
      3. Keyword matching fallback

    Sets human_review=True when confidence < LOW_CONFIDENCE_THRESHOLD.
    """
    query = state.get("query", "")
    errors = state.get("errors", [])
    llm_used = "none"

    # --- Attempt 1: Primary LLM ---
    llm = None
    content = None
    try:
        llm = _get_llm_primary()
        prompt = SYSTEM_PROMPT.format(
            intents=", ".join(VALID_INTENTS),
            query=query,
        )
        response = llm.invoke(prompt)
        content = response.content.strip()
        llm_used = "primary"
    except Exception as e1:
        errors.append(f"Primary LLM failed: {e1}")

        # --- Attempt 2: Local Ollama ---
        try:
            llm = _get_llm_ollama()
            prompt = SYSTEM_PROMPT.format(
                intents=", ".join(VALID_INTENTS),
                query=query,
            )
            response = llm.invoke(prompt)
            content = str(response.content).strip()
            llm_used = "ollama"
        except Exception as e2:
            errors.append(f"Ollama fallback failed: {e2}")
            content = None

    # --- Attempt 3: Keyword fallback if both LLMs failed ---
    if content is None or not content.strip():
        result = _keyword_fallback(query)
        return {
            **state,
            "intent": result.intent,
            "confidence": result.confidence,
            "entities": result.entities,
            "human_review": result.confidence < LOW_CONFIDENCE_THRESHOLD,
            "errors": errors,
            "metadata": {
                **state.get("metadata", {}),
                "classify_method": "keyword_fallback",
                "classify_errors": errors,
            },
        }

    # --- Clean up and parse LLM response ---
    for marker in ["```json", "```"]:
        if content.startswith(marker):
            content = content[len(marker):]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    result = _parse_llm_json(content, query)
    return {
        **state,
        "intent": result.intent,
        "confidence": result.confidence,
        "entities": result.entities,
        "human_review": result.confidence < LOW_CONFIDENCE_THRESHOLD,
        "errors": errors if errors else None,
        "metadata": {
            **state.get("metadata", {}),
            "classify_method": llm_used,
            "classify_entities": result.entities,
        },
    }


def _parse_llm_json(content: str, query: str) -> ClassificationResult:
    """Parse LLM JSON response safely."""
    import json

    try:
        data = json.loads(content)
        intent = data.get("intent", "general")
        confidence = float(data.get("confidence", 0.5))
        entities = data.get("entities", {})

        # Validate intent
        if intent not in VALID_INTENTS:
            intent = "general"
            confidence = 0.3

        confidence = max(0.0, min(1.0, confidence))

        return ClassificationResult(
            intent=intent,
            confidence=confidence,
            entities={
                "machines": entities.get("machines", []),
                "dates": entities.get("dates", []),
                "shifts": entities.get("shifts", []),
            },
        )

    except (json.JSONDecodeError, ValueError, TypeError):
        return _keyword_fallback(query)


def _keyword_fallback(query: str) -> ClassificationResult:
    """Fallback keyword-based intent matching."""
    INTENT_KEYWORDS = {
        "oee": ["oee", "overall equipment effectiveness", "equipment availability"],
        "bottleneck": ["bottleneck", "constraint"],
        "trend": ["trend", "forecast", "projection", "time series"],
        "cost": ["cost", "scrap", "rework", "waste", "roi"],
        "safety": ["safety", "incident", "osha", "compliance", "hazard"],
        "time_study": ["time study", "standard time", "cycle time"],
    }

    query_lower = query.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                return ClassificationResult(intent=intent, confidence=0.7, entities={})

    return ClassificationResult(intent="general", confidence=0.4, entities={})
