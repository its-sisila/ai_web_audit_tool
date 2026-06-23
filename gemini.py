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


# Exact system prompt from the build guide
SYSTEM_PROMPT = (
    "You are a senior web strategist and SEO analyst. You will be given factual metrics "
    "extracted from a single webpage and its cleaned text content. Your job is to generate "
    "specific, grounded insights and prioritized recommendations. Every insight must directly "
    "reference the provided metrics by their exact values — never give generic advice. "
    "Be concise, direct, and actionable."
)

# Response schema for structured output enforcement (from build guide Section 5)
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
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
    "required": ["insights", "recommendations"],
}

# Model configuration constants from the build guide
MODEL_NAME = "gemini-3.5-flash"
MAX_OUTPUT_TOKENS = 1500
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


def analyze(url: str, metrics: dict, cleaned_text: str) -> dict:
    """
    Main entry point. Sends extracted metrics and cleaned text to Gemini
    for structured AI analysis.

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
        RuntimeError: If the Gemini API call fails.
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

    # Gemini config for logging
    gemini_config = {
        "model": MODEL_NAME,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "response_mime_type": "application/json",
    }

    try:
        # Initialize the Gemini client
        client = genai.Client(api_key=api_key)

        # Call the Gemini API with structured output enforcement
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )

        # Extract raw response text
        raw_output = response.text

        # Parse the structured JSON response
        ai_result = json.loads(raw_output)

        return {
            "ai_result": ai_result,
            "raw_output": raw_output,
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": user_prompt,
            "gemini_config": gemini_config,
        }

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Gemini response as JSON: {e}")
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}")
