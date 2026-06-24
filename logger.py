"""
logger.py — Prompt log writer for audit transparency.

Saves a structured log entry to a Supabase database after every audit run.
Contains the exact system prompt, dynamically constructed user prompt,
Gemini config, extracted metrics, and raw model response.
"""

import json
import os
from datetime import datetime, timezone
from supabase import create_client, Client

# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Warning: Failed to initialize Supabase client: {e}")

def log(
    url: str,
    system_prompt: str,
    user_prompt: str,
    gemini_config: dict,
    extracted_metrics: dict,
    raw_model_response: str,
    grounding_check: dict | None = None,
) -> None:
    """
    Append a structured log entry to the Supabase prompt_logs table.
    """
    if not supabase:
        print("Warning: Supabase client not initialized. Skipping log.")
        return

    entry = {
        "url": url,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "gemini_config": gemini_config,
        "extracted_metrics": extracted_metrics,
        "raw_model_response": raw_model_response,
        "grounding_check": grounding_check,
    }

    try:
        supabase.table("prompt_logs").insert(entry).execute()
    except Exception as e:
        print(f"Warning: Failed to insert log to Supabase: {e}")


def get_last_log() -> dict | None:
    """
    Return the last entry from Supabase prompt_logs table.
    """
    if not supabase:
        return None

    try:
        response = supabase.table("prompt_logs").select("*").order("created_at", desc=True).limit(1).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        print(f"Warning: Failed to fetch last log from Supabase: {e}")
        return None

    return None


def get_history(limit: int = 10) -> list[dict]:
    """
    Return the last `limit` prompt log entries from Supabase.
    Parses raw_model_response to extract the full AI payload so the frontend
    can immediately rehydrate the UI without re-scraping.
    """
    if not supabase:
        return []

    try:
        response = supabase.table("prompt_logs").select("*").order("created_at", desc=True).limit(limit).execute()
        
        history = []
        for entry in response.data:
            try:
                ai_data = json.loads(entry["raw_model_response"])
                history.append({
                    "timestamp": entry["created_at"],
                    "url": entry["url"],
                    "overall_score": ai_data.get("overall_score"),
                    "score_breakdown": ai_data.get("score_breakdown"),
                    "competitive_context": ai_data.get("competitive_context"),
                    "metrics": entry["extracted_metrics"],
                    "insights": ai_data.get("insights"),
                    "recommendations": ai_data.get("recommendations"),
                    "grounding_check": entry.get("grounding_check"),
                })
            except json.JSONDecodeError:
                continue
        return history
    except Exception as e:
        print(f"Warning: Failed to fetch history from Supabase: {e}")
        return []
