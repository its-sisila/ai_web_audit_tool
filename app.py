"""
app.py — Flask server and route handlers for the Website Audit Tool.

Routes:
    GET  /          → Serve index.html
    POST /audit     → Run scraper → Gemini → logger, return results
    GET  /last-log  → Return the last prompt log entry
"""

import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from scraper import scrape
from gemini import analyze
from grounding import verify_grounding
from logger import log, get_last_log, get_history


# Load environment variables from .env
load_dotenv()

app = Flask(__name__)


def _is_valid_url(url: str) -> bool:
    """Basic URL validation — must have a scheme and network location."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


@app.route("/")
def index():
    """Serve the single-page UI."""
    return render_template("index.html")


@app.route("/audit", methods=["POST"])
def audit():
    """
    Accept a URL, run the full audit pipeline, and return results.

    Request body: { "url": "https://example.com" }

    Response (200):
    {
        "metrics": { ... },
        "insights": { ... },
        "recommendations": [ ... ]
    }

    Error responses:
        400 — Missing or invalid URL
        500 — Scrape or AI failure
    """
    # Parse and validate the URL
    data = request.get_json(silent=True)
    if not data or not data.get("url"):
        return jsonify({"error": "Missing 'url' in request body."}), 400

    url = data["url"].strip()

    # Normalize URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not _is_valid_url(url):
        return jsonify({"error": f"Invalid URL: {url}"}), 400

    # Step 1: Scrape the page for factual metrics
    try:
        scrape_result = scrape(url)
        metrics = scrape_result["metrics"]
        cleaned_text = scrape_result["cleaned_text"]
    except Exception as e:
        return jsonify({"error": f"Scraping failed: {str(e)}"}), 500

    # Step 2: Analyze with Gemini AI
    try:
        gemini_result = analyze(url, metrics, cleaned_text)
        ai_result = gemini_result["ai_result"]
        raw_output = gemini_result["raw_output"]
        system_prompt = gemini_result["system_prompt"]
        user_prompt = gemini_result["user_prompt"]
        gemini_config = gemini_result["gemini_config"]
    except Exception as e:
        return jsonify({"error": f"AI analysis failed: {str(e)}"}), 500

    # Step 2b: Verify grounding — check that AI insights cite real metrics
    grounding_result = verify_grounding(
        ai_result.get("insights", {}), metrics
    )

    # Step 3: Log the full prompt exchange
    try:
        log(
            url=url,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            gemini_config=gemini_config,
            extracted_metrics=metrics,
            raw_model_response=raw_output,
            grounding_check=grounding_result,
        )
    except Exception as e:
        # Log failure shouldn't break the response — just warn
        print(f"Warning: Failed to write prompt log: {e}")

    # Step 4: Return structured response
    return jsonify({
        "metrics": metrics,
        "overall_score": ai_result.get("overall_score", 0),
        "score_breakdown": ai_result.get("score_breakdown", {}),
        "competitive_context": ai_result.get("competitive_context", ""),
        "insights": ai_result.get("insights", {}),
        "recommendations": ai_result.get("recommendations", []),
        "grounding_check": grounding_result,
    })


@app.route("/last-log", methods=["GET"])
def last_log():
    """Return the last entry from prompt_log.json."""
    entry = get_last_log()
    if entry is None:
        return jsonify({"error": "No audit logs found."}), 404
    return jsonify(entry)


@app.route("/history", methods=["GET"])
def history():
    """Return the last 10 audits with full UI data for quick re-rendering."""
    return jsonify(get_history(10))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
