"""
logger.py — Prompt log writer for audit transparency.

Appends a structured log entry to prompt_log.json after every audit run.
Contains the exact system prompt, dynamically constructed user prompt,
Gemini config, extracted metrics, and raw model response.
"""

import json
import os
from datetime import datetime, timezone


# Path to the prompt log file (project root)
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_log.json")


def log(
    url: str,
    system_prompt: str,
    user_prompt: str,
    gemini_config: dict,
    extracted_metrics: dict,
    raw_model_response: str,
) -> None:
    """
    Append a structured log entry to prompt_log.json.

    Each entry follows the exact schema from the build guide Section 6:
    {
        "timestamp": "ISO-8601",
        "url": "...",
        "system_prompt": "...",
        "user_prompt": "...",
        "gemini_config": {
            "model": "gemini-3.5-flash",
            "max_output_tokens": 1500,
            "response_mime_type": "application/json"
        },
        "extracted_metrics": { ... },
        "raw_model_response": "..."
    }

    Args:
        url: The audited URL.
        system_prompt: The exact system prompt sent to Gemini.
        user_prompt: The dynamically constructed user prompt with metrics.
        gemini_config: Dict with model, max_output_tokens, response_mime_type.
        extracted_metrics: The factual metrics dict from the scraper.
        raw_model_response: The raw string response from Gemini before parsing.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "gemini_config": gemini_config,
        "extracted_metrics": extracted_metrics,
        "raw_model_response": raw_model_response,
    }

    # Read existing log entries (or start with empty list)
    entries = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    entries = json.loads(content)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, start fresh
            entries = []

    # Append the new entry
    entries.append(entry)

    # Write back the full array
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def get_last_log() -> dict | None:
    """
    Read prompt_log.json and return the last entry.
    Returns None if the file doesn't exist or is empty.
    """
    if not os.path.exists(LOG_FILE):
        return None

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return None
            entries = json.loads(content)
            if entries:
                return entries[-1]
    except (json.JSONDecodeError, IOError):
        return None

    return None
