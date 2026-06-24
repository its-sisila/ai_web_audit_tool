"""
gemini.py — AI insights engine using Google Gemini API.

This module is fully independent of the scraper layer.
It accepts pre-extracted metrics and cleaned text, then returns
structured AI insights and recommendations.
No scraper imports exist in this file.
"""

import json
import os

from google import genai
from google.genai import types


# Exact system prompt from the build guide, enhanced with industry benchmarks
SYSTEM_PROMPT = (
    "You are a senior web strategist and SEO analyst. You will be given factual metrics "
    "extracted from a single webpage and its cleaned text content. Your job is to generate "
    "specific, grounded insights and prioritized recommendations. Every insight must directly "
    "reference the provided metrics by their exact values — never give generic advice. "
    "Be concise, direct, and actionable.\n\n"
    "Use these industry benchmarks for comparison:\n"
    "- Word count: High-performing marketing pages have 800–2000 words\n"
    "- Heading structure: 1 H1 (mandatory), 3–8 H2s, H3s as needed\n"
    "- CTA density: 2–5 CTAs per 1000 words is optimal\n"
    "- Image alt text: ≥ 95% coverage is the accessibility standard\n"
    "- Meta description: 120–160 characters for optimal SERP display\n"
    "- Internal links: 3–5 per 1000 words for good site navigation\n"
    "When referencing benchmarks, explicitly state the comparison "
    "(e.g., '555 words is 31% below the 800-word minimum for marketing pages').\n\n"
    "Assign an overall_score (0–100) and per-pillar scores in score_breakdown. "
    "A score of 80+ means strong performance; 50–79 means needs improvement; below 50 is poor. "
    "Base scores on the benchmarks provided and the extracted metrics."
)

# Response schema for structured output enforcement (from build guide Section 5),
# enhanced with scoring and competitive context fields.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {
            "type": "integer",
            "description": "Overall page quality score from 0–100 based on all metrics and analysis.",
        },
        "score_breakdown": {
            "type": "object",
            "properties": {
                "seo_structure": {"type": "integer"},
                "messaging_clarity": {"type": "integer"},
                "cta_usage": {"type": "integer"},
                "content_depth": {"type": "integer"},
                "ux_structural_concerns": {"type": "integer"},
            },
            "required": [
                "seo_structure",
                "messaging_clarity",
                "cta_usage",
                "content_depth",
                "ux_structural_concerns",
            ],
        },
        "competitive_context": {
            "type": "string",
            "description": (
                "1-2 sentence summary comparing this page to typical "
                "high-performing marketing sites in its apparent industry."
            ),
        },
        "insights": {
            "type": "object",
            "properties": {
                "seo_structure": {"type": "string"},
                "messaging_clarity": {"type": "string"},
                "cta_usage": {"type": "string"},
                "content_depth": {"type": "string"},
                "ux_structural_concerns": {"type": "string"},
            },
            "required": [
                "seo_structure",
                "messaging_clarity",
                "cta_usage",
                "content_depth",
                "ux_structural_concerns",
            ],
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "priority": {
                        "type": "string",
                        "enum": ["High", "Medium", "Low"],
                    },
                    "recommendation": {"type": "string"},
                    "reasoning": {"type": "string"},
                },
                "required": ["priority", "recommendation", "reasoning"],
            },
            "minItems": 3,
            "maxItems": 5,
        },
    },
    "required": [
        "overall_score",
        "score_breakdown",
        "competitive_context",
        "insights",
        "recommendations",
    ],
}

# Model fallback chain — tried in order; first available model wins.
# 503/UNAVAILABLE errors trigger the next model in the list.
# Only the successful call consumes free tier quota.
MODEL_CHAIN = [
    "gemini-3.5-flash",       # Primary — specified in the build guide
    "gemini-3.1-flash-lite",  # Fallback 1 — newer lite model
    "gemini-2.5-flash",       # Fallback 2 — stable, widely available
    "gemini-2.5-flash-lite",  # Fallback 3 — lighter variant

]
MAX_OUTPUT_TOKENS = 8192
MAX_CLEANED_TEXT_WORDS = 3000


def _truncate_text(text: str, max_words: int = MAX_CLEANED_TEXT_WORDS) -> str:
    """Truncate cleaned page text to a maximum number of words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _build_user_prompt(url: str, metrics: dict, cleaned_text: str) -> str:
    """
    Construct the user prompt dynamically using the exact template
    from the build guide Section 5.
    """
    truncated_text = _truncate_text(cleaned_text)

    return (
        f"Here are the extracted metrics from {url}:\n"
        f"\n"
        f"- Word Count: {metrics['word_count']}\n"
        f"- H1 Tags: {metrics['h1_count']}\n"
        f"- H2 Tags: {metrics['h2_count']}\n"
        f"- H3 Tags: {metrics['h3_count']}\n"
        f"- CTA Count: {metrics['cta_count']}\n"
        f"- Internal Links: {metrics['internal_links']}\n"
        f"- External Links: {metrics['external_links']}\n"
        f"- Total Images: {metrics['image_count']}\n"
        f"- Images Missing Alt Text: {metrics['images_missing_alt_pct']}%\n"
        f"- Meta Title: {metrics['meta_title']}\n"
        f"- Meta Description: {metrics['meta_description']}\n"
        f"\n"
        f"Here is the cleaned page text (truncated to 3000 words):\n"
        f"{truncated_text}\n"
        f"\n"
        f"Generate structured insights and 3–5 prioritized recommendations grounded in these metrics."
    )


def _call_gemini(client, model_name: str, user_prompt: str) -> str:
    """
    Make a single Gemini API call and return the raw response text.
    Raises on failure so the caller can decide whether to retry.
    """
    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )
    return response.text


def analyze(url: str, metrics: dict, cleaned_text: str) -> dict:
    """
    Main entry point. Sends extracted metrics and cleaned text to Gemini
    for structured AI analysis.

    Tries models in priority order (gemini-3.5-flash → 2.5-flash → lite variants).
    Falls back to the next model on 503 UNAVAILABLE errors.

    Args:
        url: The original URL being audited.
        metrics: Dict of factual metrics from the scraper.
        cleaned_text: Visible body text from the scraper.

    Returns:
        {
            "ai_result": {
                "insights": { ... },
                "recommendations": [ ... ]
            },
            "raw_output": str,
            "system_prompt": str,
            "user_prompt": str,
            "gemini_config": {
                "model": str,
                "max_output_tokens": int,
                "response_mime_type": str
            }
        }

    Raises:
        RuntimeError: If all models in the fallback chain fail.
        EnvironmentError: If GEMINI_API_KEY is not set.
    """
    # Load API key from environment — never hardcoded
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not found in environment. "
            "Please set it in your .env file."
        )

    # Build prompts
    user_prompt = _build_user_prompt(url, metrics, cleaned_text)

    # Initialize the Gemini client
    client = genai.Client(api_key=api_key)

    # Try each model in the chain until one succeeds
    raw_output = None
    used_model = None
    last_error = None

    for model_name in MODEL_CHAIN:
        try:
            raw_output = _call_gemini(client, model_name, user_prompt)
            used_model = model_name
            if model_name != MODEL_CHAIN[0]:
                print(f"[gemini] Succeeded with fallback model: {model_name}")
            break
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str:
                print(f"[gemini] {model_name} unavailable, trying next...")
                continue
            else:
                # Non-availability error (auth, schema, etc.) — don't retry
                raise RuntimeError(f"Gemini API call failed: {e}")

    if raw_output is None:
        raise RuntimeError(
            f"All models unavailable ({', '.join(MODEL_CHAIN)}). Last error: {last_error}"
        )

    # Gemini config for logging (reflects the model that actually responded)
    gemini_config = {
        "model": used_model,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "response_mime_type": "application/json",
    }

    try:
        ai_result = json.loads(raw_output)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Gemini response as JSON: {e}")

    return {
        "ai_result": ai_result,
        "raw_output": raw_output,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "gemini_config": gemini_config,
    }

