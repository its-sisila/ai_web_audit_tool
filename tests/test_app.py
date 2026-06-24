"""
test_app.py — Integration tests for Flask route handlers.

Mocks the scraper and gemini modules to test the audit pipeline
routes without making real HTTP or AI calls.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app


# ---------- Fixture ----------

@pytest.fixture
def client():
    """Create a Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ---------- GET / ----------

class TestIndexRoute:
    """Test the main page route."""

    def test_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_returns_html(self, client):
        response = client.get("/")
        assert b"Website Audit Tool" in response.data


# ---------- POST /audit — Validation ----------

class TestAuditValidation:
    """Test input validation on the /audit route."""

    def test_missing_body_returns_400(self, client):
        response = client.post("/audit", content_type="application/json")
        assert response.status_code == 400

    def test_empty_url_returns_400(self, client):
        response = client.post(
            "/audit",
            data=json.dumps({"url": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_missing_url_key_returns_400(self, client):
        response = client.post(
            "/audit",
            data=json.dumps({"page": "https://example.com"}),
            content_type="application/json",
        )
        assert response.status_code == 400


# ---------- POST /audit — Success Path ----------

MOCK_METRICS = {
    "word_count": 500,
    "h1_count": 1,
    "h2_count": 3,
    "h3_count": 2,
    "cta_count": 5,
    "internal_links": 10,
    "external_links": 3,
    "image_count": 4,
    "images_missing_alt_pct": 25.0,
    "meta_title": "Test Title",
    "meta_description": "Test description.",
}

MOCK_AI_RESULT = {
    "overall_score": 72,
    "score_breakdown": {
        "seo_structure": 80,
        "messaging_clarity": 70,
        "cta_usage": 65,
        "content_depth": 60,
        "ux_structural_concerns": 75,
    },
    "competitive_context": "Comparable to mid-tier SaaS marketing pages.",
    "insights": {
        "seo_structure": "With 1 H1 and 3 H2 tags, structure is solid.",
        "messaging_clarity": "Test Title is clear and descriptive.",
        "cta_usage": "5 CTAs for 500 words is within the optimal range.",
        "content_depth": "500 words is below the 800-word benchmark.",
        "ux_structural_concerns": "25.0% missing alt text needs attention.",
    },
    "recommendations": [
        {"priority": "High", "recommendation": "Expand content", "reasoning": "Below benchmark."},
        {"priority": "Medium", "recommendation": "Fix alt text", "reasoning": "Accessibility."},
        {"priority": "Low", "recommendation": "Add more internal links", "reasoning": "Navigation."},
    ],
}

MOCK_GEMINI_RETURN = {
    "ai_result": MOCK_AI_RESULT,
    "raw_output": json.dumps(MOCK_AI_RESULT),
    "system_prompt": "You are a senior web strategist.",
    "user_prompt": "Metrics for https://example.com...",
    "gemini_config": {
        "model": "gemini-3.5-flash",
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    },
}


class TestAuditSuccess:
    """Test the /audit route with mocked scraper and gemini."""

    @pytest.fixture(autouse=True)
    def _mock_dependencies(self, monkeypatch, tmp_path):
        """Mock scraper, gemini, and logger to isolate route logic."""
        monkeypatch.setattr(
            "app.scrape",
            lambda url: {"metrics": MOCK_METRICS, "cleaned_text": "Some page text."},
        )
        monkeypatch.setattr(
            "app.analyze",
            lambda url, metrics, text: MOCK_GEMINI_RETURN,
        )
        # Redirect logger to a temp file to avoid polluting project root
        monkeypatch.setattr("app.log", lambda **kwargs: None)

    def test_returns_200(self, client):
        response = client.post(
            "/audit",
            data=json.dumps({"url": "https://example.com"}),
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_response_has_all_fields(self, client):
        response = client.post(
            "/audit",
            data=json.dumps({"url": "https://example.com"}),
            content_type="application/json",
        )
        data = response.get_json()
        assert "metrics" in data
        assert "overall_score" in data
        assert "score_breakdown" in data
        assert "competitive_context" in data
        assert "insights" in data
        assert "recommendations" in data
        assert "grounding_check" in data

    def test_grounding_check_included(self, client):
        response = client.post(
            "/audit",
            data=json.dumps({"url": "https://example.com"}),
            content_type="application/json",
        )
        data = response.get_json()
        gc = data["grounding_check"]
        assert "overall_grounded_pct" in gc
        assert "seo_structure" in gc

    def test_url_normalization(self, client):
        """URLs without scheme should be auto-prefixed with https://."""
        response = client.post(
            "/audit",
            data=json.dumps({"url": "example.com"}),
            content_type="application/json",
        )
        assert response.status_code == 200


# ---------- GET /last-log ----------

class TestLastLogRoute:
    """Test the /last-log route."""

    def test_no_logs_returns_404(self, client, monkeypatch):
        monkeypatch.setattr("app.get_last_log", lambda: None)
        response = client.get("/last-log")
        assert response.status_code == 404
