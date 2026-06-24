"""
grounding.py — Post-AI grounding verification.

Checks whether each AI insight string references specific metric values
from the scraper output. This is NOT an AI call — it's deterministic
string matching that validates the AI did its job.

This module is fully independent — no AI imports, no scraper imports.
"""

from typing import TypedDict


# ---------- Type Definitions ----------

class InsightGrounding(TypedDict):
    """Grounding result for a single insight."""
    grounded: bool
    cited_metrics: list[str]


class GroundingResult(TypedDict):
    """Full grounding verification result."""
    seo_structure: InsightGrounding
    messaging_clarity: InsightGrounding
    cta_usage: InsightGrounding
    content_depth: InsightGrounding
    ux_structural_concerns: InsightGrounding
    overall_grounded_pct: float


# Maps insight keys to the metric keys they should reference.
# Each insight is expected to cite at least one of its mapped metrics.
INSIGHT_METRIC_MAP = {
    "seo_structure": [
        "h1_count", "h2_count", "h3_count", "meta_title", "meta_title_length", "meta_description", "meta_description_length",
    ],
    "messaging_clarity": [
        "meta_title", "meta_title_length", "meta_description", "meta_description_length", "word_count",
    ],
    "cta_usage": [
        "cta_count", "word_count",
    ],
    "content_depth": [
        "word_count", "h2_count", "h3_count",
    ],
    "ux_structural_concerns": [
        "images_missing_alt_pct", "image_count", "internal_links", "external_links",
    ],
}


def verify_grounding(insights: dict, metrics: dict) -> GroundingResult:
    """
    For each insight, check if the text contains at least one
    of the expected metric values as a literal string.

    Every insight is required to be grounded — the overall_grounded_pct
    reflects the percentage of insights that cite specific metrics.

    Args:
        insights: Dict of insight strings keyed by pillar name.
        metrics: Dict of factual metrics from the scraper.

    Returns:
        {
            "seo_structure": {
                "grounded": True,
                "cited_metrics": ["h1_count", "h2_count"]
            },
            ...
            "overall_grounded_pct": 80.0
        }
    """
    result = {}
    grounded_count = 0

    for insight_key, expected_metrics in INSIGHT_METRIC_MAP.items():
        insight_text = insights.get(insight_key, "")
        cited = []

        for metric_key in expected_metrics:
            value = metrics.get(metric_key)
            if value is None:
                continue

            # Convert value to string for matching
            value_str = str(value)

            # Check for the value in the insight text
            if value_str in insight_text:
                cited.append(metric_key)

        is_grounded = len(cited) > 0
        if is_grounded:
            grounded_count += 1

        result[insight_key] = {
            "grounded": is_grounded,
            "cited_metrics": cited,
        }

    total = len(INSIGHT_METRIC_MAP)
    result["overall_grounded_pct"] = (
        round((grounded_count / total) * 100, 1) if total else 0.0
    )

    return result
