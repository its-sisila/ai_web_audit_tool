"""
test_scraper.py — Unit tests for the scraper module.

Uses HTML fixtures and mocks requests.get to test metric extraction
without making real HTTP calls.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

# Add project root to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper import scrape, _clean_soup, _count_headings, _count_ctas, _analyze_images, _extract_meta
from bs4 import BeautifulSoup


# ---------- Fixture Helpers ----------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(filename: str) -> str:
    """Load an HTML fixture file."""
    with open(os.path.join(FIXTURES_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()


def _mock_response(html: str) -> MagicMock:
    """Create a mock requests.Response with the given HTML."""
    mock = MagicMock()
    mock.text = html
    mock.raise_for_status = MagicMock()
    return mock


# ---------- Happy Path Tests ----------

class TestScrapeHappyPath:
    """Test scraper with a fully populated sample page."""

    @patch("scraper.requests.get")
    def test_returns_metrics_and_cleaned_text(self, mock_get):
        html = _load_fixture("sample_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")

        assert "metrics" in result
        assert "cleaned_text" in result
        assert isinstance(result["metrics"], dict)
        assert isinstance(result["cleaned_text"], str)

    @patch("scraper.requests.get")
    def test_word_count_is_positive(self, mock_get):
        html = _load_fixture("sample_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        assert result["metrics"]["word_count"] > 0

    @patch("scraper.requests.get")
    def test_heading_counts(self, mock_get):
        html = _load_fixture("sample_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        m = result["metrics"]
        assert m["h1_count"] == 1
        assert m["h2_count"] == 2
        assert m["h3_count"] == 2

    @patch("scraper.requests.get")
    def test_cta_count(self, mock_get):
        html = _load_fixture("sample_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        # 1 button (Get Started) + 2 CTA anchors (Sign Up, Book a Demo)
        assert result["metrics"]["cta_count"] == 3

    @patch("scraper.requests.get")
    def test_link_counts(self, mock_get):
        html = _load_fixture("sample_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        m = result["metrics"]
        # /about, /pricing, /signup, /demo = 4 internal
        assert m["internal_links"] == 4
        # external.com, other.com = 2 external
        assert m["external_links"] == 2

    @patch("scraper.requests.get")
    def test_image_analysis(self, mock_get):
        html = _load_fixture("sample_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        m = result["metrics"]
        assert m["image_count"] == 4
        # 2 out of 4 missing alt text = 50.0%
        assert m["images_missing_alt_pct"] == 50.0

    @patch("scraper.requests.get")
    def test_meta_extraction(self, mock_get):
        html = _load_fixture("sample_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        m = result["metrics"]
        assert m["meta_title"] == "Test Page Title"
        assert m["meta_description"] == "A test page for the web audit scraper."

    @patch("scraper.requests.get")
    def test_script_and_style_removed_from_text(self, mock_get):
        html = _load_fixture("sample_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        assert "should be removed" not in result["cleaned_text"]
        assert "display: none" not in result["cleaned_text"]


# ---------- Empty Page Tests ----------

class TestScrapeEmptyPage:
    """Test scraper with a minimal empty page."""

    @patch("scraper.requests.get")
    def test_empty_page_returns_zero_metrics(self, mock_get):
        html = _load_fixture("empty_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        m = result["metrics"]
        assert m["word_count"] == 0
        assert m["h1_count"] == 0
        assert m["h2_count"] == 0
        assert m["h3_count"] == 0
        assert m["cta_count"] == 0
        assert m["image_count"] == 0

    @patch("scraper.requests.get")
    def test_empty_page_has_no_meta(self, mock_get):
        html = _load_fixture("empty_page.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        m = result["metrics"]
        assert m["meta_title"] is None
        assert m["meta_description"] is None


# ---------- Missing Meta Tests ----------

class TestScrapeMissingMeta:
    """Test scraper with a page that has a title but no meta description."""

    @patch("scraper.requests.get")
    def test_title_present_description_missing(self, mock_get):
        html = _load_fixture("missing_meta.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        m = result["metrics"]
        assert m["meta_title"] == "Missing Meta"
        assert m["meta_description"] is None

    @patch("scraper.requests.get")
    def test_all_images_missing_alt(self, mock_get):
        html = _load_fixture("missing_meta.html")
        mock_get.return_value = _mock_response(html)

        result = scrape("https://example.com")
        m = result["metrics"]
        assert m["image_count"] == 2
        assert m["images_missing_alt_pct"] == 100.0


# ---------- Input Validation Tests ----------

class TestScrapeInputValidation:
    """Test scraper input validation."""

    def test_empty_url_raises_value_error(self):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            scrape("")

    def test_whitespace_url_raises_value_error(self):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            scrape("   ")
