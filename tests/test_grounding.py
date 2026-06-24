"""
test_grounding.py — Unit tests for the grounding verification module.

Tests the deterministic string-matching logic that validates whether
AI insights cite real metric values from the scraper.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from grounding import verify_grounding


# ---------- Sample Data ----------

SAMPLE_METRICS = {
    "word_count": 501,
    "h1_count": 1,
    "h2_count": 17,
    "h3_count": 6,
    "cta_count": 12,
    "internal_links": 141,
    "external_links": 17,
    "image_count": 18,
    "images_missing_alt_pct": 16.7,
    "meta_title": "Agentic Infrastructure",
    "meta_description": "The autonomous stack for every app and agent.",
}


# ---------- Fully Grounded ----------

class TestFullyGrounded:
    """Test with insights that all cite real metric values."""

    def test_all_insights_grounded(self):
        insights = {
            "seo_structure": "With 17 H2 tags and 6 H3 tags for only 501 words, the structure is fragmented.",
            "messaging_clarity": "The title 'Agentic Infrastructure' is crisp and direct.",
            "cta_usage": "At 12 CTAs for 501 words, the density is excessive.",
            "content_depth": "The 501-word count is below the 800-word benchmark.",
            "ux_structural_concerns": "16.7% of images missing alt text fails the accessibility standard.",
        }

        result = verify_grounding(insights, SAMPLE_METRICS)

        assert result["overall_grounded_pct"] == 100.0
        for key in insights:
            assert result[key]["grounded"] is True
            assert len(result[key]["cited_metrics"]) > 0

    def test_cited_metrics_are_correct(self):
        insights = {
            "seo_structure": "With 1 H1, 17 H2, and 6 H3 tags.",
            "messaging_clarity": "The meta title 'Agentic Infrastructure' works well.",
            "cta_usage": "12 CTAs across 501 words is too many.",
            "content_depth": "Only 501 words on the page.",
            "ux_structural_concerns": "16.7% missing alt text out of 18 images.",
        }

        result = verify_grounding(insights, SAMPLE_METRICS)

        assert "h1_count" in result["seo_structure"]["cited_metrics"]
        assert "h2_count" in result["seo_structure"]["cited_metrics"]
        assert "cta_count" in result["cta_usage"]["cited_metrics"]
        assert "images_missing_alt_pct" in result["ux_structural_concerns"]["cited_metrics"]


# ---------- Partially Grounded ----------

class TestPartiallyGrounded:
    """Test with some insights grounded and some not."""

    def test_partial_grounding(self):
        insights = {
            "seo_structure": "With 17 H2 tags, the heading structure is too dense.",
            "messaging_clarity": "The messaging is clear and compelling.",  # No metric cited!
            "cta_usage": "12 CTAs is too many for a page this size.",
            "content_depth": "The page lacks content depth.",  # No metric cited!
            "ux_structural_concerns": "16.7% of images are missing alt text.",
        }

        result = verify_grounding(insights, SAMPLE_METRICS)

        assert result["seo_structure"]["grounded"] is True
        assert result["messaging_clarity"]["grounded"] is False
        assert result["cta_usage"]["grounded"] is True
        assert result["content_depth"]["grounded"] is False
        assert result["ux_structural_concerns"]["grounded"] is True
        assert result["overall_grounded_pct"] == 60.0


# ---------- Fully Ungrounded ----------

class TestFullyUngrounded:
    """Test with insights that cite no metric values at all."""

    def test_zero_grounding(self):
        insights = {
            "seo_structure": "The heading structure needs improvement.",
            "messaging_clarity": "The messaging could be clearer.",
            "cta_usage": "There are too many calls to action.",
            "content_depth": "The page needs more content.",
            "ux_structural_concerns": "Accessibility should be improved.",
        }

        result = verify_grounding(insights, SAMPLE_METRICS)

        assert result["overall_grounded_pct"] == 0.0
        for key in insights:
            assert result[key]["grounded"] is False
            assert result[key]["cited_metrics"] == []


# ---------- Edge Cases ----------

class TestGroundingEdgeCases:
    """Test edge cases for the grounding module."""

    def test_empty_insights(self):
        result = verify_grounding({}, SAMPLE_METRICS)
        assert result["overall_grounded_pct"] == 0.0

    def test_empty_metrics(self):
        insights = {
            "seo_structure": "Some generic analysis.",
        }
        result = verify_grounding(insights, {})
        assert result["seo_structure"]["grounded"] is False

    def test_missing_insight_keys(self):
        """Insights dict missing some expected keys — should still work."""
        insights = {
            "seo_structure": "With 17 H2 tags, structure is dense.",
        }
        result = verify_grounding(insights, SAMPLE_METRICS)
        assert result["seo_structure"]["grounded"] is True
        assert result["messaging_clarity"]["grounded"] is False
