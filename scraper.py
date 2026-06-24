"""
scraper.py — Factual metrics extraction from a single webpage.

This module is fully independent of the AI layer.
It accepts a URL, fetches the HTML, and extracts structured metrics.
No Gemini or AI imports exist in this file.
"""

import re
from typing import TypedDict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Comment


# ---------- Type Definitions ----------

class ScrapeMetrics(TypedDict):
    """Structured metrics extracted from a webpage."""
    word_count: int
    h1_count: int
    h2_count: int
    h3_count: int
    cta_count: int
    internal_links: int
    external_links: int
    image_count: int
    images_missing_alt_pct: float
    meta_title: str | None
    meta_description: str | None


class ScrapeResult(TypedDict):
    """Return type for the scrape() function."""
    metrics: ScrapeMetrics
    cleaned_text: str


# Common CTA phrases used to identify call-to-action elements
CTA_PATTERNS = [
    r"get\s+started",
    r"sign\s+up",
    r"contact(\s+us)?",
    r"book\s+(a\s+)?(call|demo|meeting|consultation|appointment)",
    r"schedule\s+(a\s+)?(call|demo|meeting|consultation|appointment)",
    r"request\s+(a\s+)?(quote|demo|consultation|proposal|info)",
    r"free\s+trial",
    r"try\s+(it\s+)?(free|now|today)",
    r"buy\s+now",
    r"subscribe",
    r"join\s+(us|now|today|free)",
    r"start\s+(now|today|free|your)",
    r"learn\s+more",
    r"download(\s+now)?",
    r"register(\s+now)?",
    r"apply\s+now",
    r"shop\s+now",
    r"order\s+now",
    r"claim\s+your",
    r"let['']?s\s+(talk|chat|connect|go)",
]

# Compile CTA patterns into a single regex for performance
_CTA_REGEX = re.compile(
    "|".join(f"(?:{p})" for p in CTA_PATTERNS),
    re.IGNORECASE,
)

# User-Agent to mimic a standard browser request
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _fetch_html(url: str) -> str:
    """Fetch raw HTML from the given URL."""
    response = requests.get(
        url,
        headers={"User-Agent": _USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    return response.text


def _clean_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Remove <script>, <style>, <svg>, and HTML comments from the soup.
    This must run BEFORE any text extraction per the build guide.
    """
    # Remove script, style, and svg tags
    for tag in soup.find_all(["script", "style", "svg"]):
        tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    return soup


def _extract_visible_text(soup: BeautifulSoup) -> str:
    """Extract visible body text after cleaning."""
    body = soup.find("body")
    if not body:
        return ""
    return body.get_text(separator=" ", strip=True)


def _count_words(text: str) -> int:
    """Count words in visible text."""
    return len(text.split())


def _count_headings(soup: BeautifulSoup) -> dict:
    """Count H1, H2, H3 tags separately."""
    return {
        "h1_count": len(soup.find_all("h1")),
        "h2_count": len(soup.find_all("h2")),
        "h3_count": len(soup.find_all("h3")),
    }


def _is_cta_text(text: str) -> bool:
    """Check if text matches common CTA patterns."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_CTA_REGEX.search(cleaned))


def _count_ctas(soup: BeautifulSoup) -> int:
    """
    Count CTA elements: all <button> elements plus <a> tags
    whose visible text matches CTA patterns.
    """
    count = 0

    # All buttons count as CTAs
    count += len(soup.find_all("button"))

    # Anchor tags with CTA-like text
    for a_tag in soup.find_all("a"):
        link_text = a_tag.get_text(strip=True)
        if _is_cta_text(link_text):
            count += 1

    return count


def _count_links(soup: BeautifulSoup, base_domain: str) -> dict:
    """
    Categorize links as internal or external by comparing
    the href domain against the input URL's domain.
    """
    internal = 0
    external = 0

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]

        # Skip anchors, mailto, tel, javascript
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        parsed = urlparse(href)

        # Relative links are internal
        if not parsed.netloc:
            internal += 1
        elif parsed.netloc.lower().replace("www.", "") == base_domain:
            internal += 1
        else:
            external += 1

    return {
        "internal_links": internal,
        "external_links": external,
    }


def _analyze_images(soup: BeautifulSoup) -> dict:
    """
    Count total <img> tags and calculate the percentage
    of images missing alt text.
    """
    images = soup.find_all("img")
    total = len(images)

    if total == 0:
        return {
            "image_count": 0,
            "images_missing_alt_pct": 0.0,
        }

    missing_alt = sum(
        1 for img in images
        if not img.get("alt", "").strip()
    )

    return {
        "image_count": total,
        "images_missing_alt_pct": round((missing_alt / total) * 100, 1),
    }


def _extract_meta(soup: BeautifulSoup) -> dict:
    """Extract meta title and meta description."""
    # Meta title from <title> tag
    title_tag = soup.find("title")
    meta_title = title_tag.get_text(strip=True) if title_tag else None

    # Meta description from <meta name="description">
    desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = desc_tag.get("content", "").strip() if desc_tag else None

    # Normalize empty strings to None
    if meta_description == "":
        meta_description = None

    return {
        "meta_title": meta_title,
        "meta_description": meta_description,
    }


def scrape(url: str) -> ScrapeResult:
    """
    Main entry point. Accepts a URL, fetches the page, and extracts
    all factual metrics plus cleaned body text.

    Returns:
        {
            "metrics": {
                "word_count": int,
                "h1_count": int,
                "h2_count": int,
                "h3_count": int,
                "cta_count": int,
                "internal_links": int,
                "external_links": int,
                "image_count": int,
                "images_missing_alt_pct": float,
                "meta_title": str | None,
                "meta_description": str | None
            },
            "cleaned_text": str
        }

    Raises:
        requests.RequestException: If the URL is unreachable or returns an error.
        ValueError: If the URL is empty or malformed.
    """
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")

    # Normalize URL
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Parse base domain for link comparison
    parsed_url = urlparse(url)
    base_domain = parsed_url.netloc.lower().replace("www.", "")

    # Fetch and parse HTML
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    # Clean the soup BEFORE any extraction
    soup = _clean_soup(soup)

    # Extract visible text
    cleaned_text = _extract_visible_text(soup)

    # Build metrics dict
    metrics = {
        "word_count": _count_words(cleaned_text),
        **_count_headings(soup),
        "cta_count": _count_ctas(soup),
        **_count_links(soup, base_domain),
        **_analyze_images(soup),
        **_extract_meta(soup),
    }

    return {
        "metrics": metrics,
        "cleaned_text": cleaned_text,
    }
