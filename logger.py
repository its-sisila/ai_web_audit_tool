"""
logger.py — Prompt log writer for audit transparency.

Saves a structured log entry to a Supabase database after every audit run.
If Supabase is not configured (e.g. local development), falls back to prompt_log.json.
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

# Path to the prompt log file (project root) for local fallback
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_log.json")

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
    Append a structured log entry to the Supabase prompt_logs table,
    or locally to prompt_log.json if Supabase is unavailable.
    """
    entry = {
        "url": url,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "gemini_config": gemini_config,
        "extracted_metrics": extracted_metrics,
        "raw_model_response": raw_model_response,
        "grounding_check": grounding_check,
    }

    if supabase:
        try:
            supabase.table("prompt_logs").insert(entry).execute()
            return
        except Exception as e:
            print(f"Warning: Failed to insert log to Supabase: {e}. Falling back to local file.")
    
    # Local fallback
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    entries = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    entries = json.loads(content)
        except (json.JSONDecodeError, IOError):
            entries = []

    entries.append(entry)
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Warning: Failed to write to local log file: {e}")


def get_last_log() -> dict | None:
    """
    Return the last entry from Supabase prompt_logs table,
    or locally from prompt_log.json.
    """
    if supabase:
        try:
            response = supabase.table("prompt_logs").select("*").order("created_at", desc=True).limit(1).execute()
            if response.data:
                return response.data[0]
        except Exception as e:
            print(f"Warning: Failed to fetch last log from Supabase: {e}. Falling back to local file.")

    # Local fallback
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


def get_history(limit: int = 10) -> list[dict]:
    """
    Return the last `limit` prompt log entries from Supabase or locally.
    """
    if supabase:
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
            print(f"Warning: Failed to fetch history from Supabase: {e}. Falling back to local file.")

    # Local fallback
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            entries = json.loads(content)
            
            history = []
            for entry in reversed(entries[-limit:]):
                try:
                    ai_data = json.loads(entry["raw_model_response"])
                    history.append({
                        "timestamp": entry.get("timestamp", ""),
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
    except (json.JSONDecodeError, IOError):
        return []
