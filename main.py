from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv
from datetime import date
import os
import json
import requests

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
daily_request_limit = int(os.getenv("DAILY_REQUEST_LIMIT", "25"))

app = FastAPI()


class ParseRequest(BaseModel):
    text: str
    user_id: str | None = None


def resolve_user_id(request: ParseRequest, x_user_id: str | None) -> str | None:
    return request.user_id or x_user_id


def get_usage_count(user_id: str, usage_date: str) -> int:
    if not supabase_url or not supabase_service_role_key:
        raise RuntimeError("Supabase credentials are not configured")
    response = requests.get(
        f"{supabase_url}/rest/v1/usage_log",
        params={
            "select": "request_count",
            "user_id": f"eq.{user_id}",
            "usage_date": f"eq.{usage_date}",
            "limit": 1,
        },
        headers={
            "apikey": supabase_service_role_key,
            "Authorization": f"Bearer {supabase_service_role_key}",
        },
        timeout=10,
    )
    response.raise_for_status()
    rows = response.json()
    if not rows:
        return 0
    return int(rows[0].get("request_count", 0))


def save_usage_count(user_id: str, usage_date: str, request_count: int) -> None:
    if not supabase_url or not supabase_service_role_key:
        raise RuntimeError("Supabase credentials are not configured")
    response = requests.post(
        f"{supabase_url}/rest/v1/usage_log",
        json={
            "user_id": user_id,
            "usage_date": usage_date,
            "request_count": request_count,
        },
        params={"on_conflict": "user_id,usage_date"},
        headers={
            "apikey": supabase_service_role_key,
            "Authorization": f"Bearer {supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        timeout=10,
    )
    response.raise_for_status()


@app.post("/parse-input")
def parse_input(request: ParseRequest, x_user_id: str | None = Header(default=None)):
    today = date.today().isoformat()
    user_id = resolve_user_id(request, x_user_id)

    if not user_id:
        raise HTTPException(status_code=401, detail="user_id is required")

    current_count = get_usage_count(user_id, today)
    if current_count >= daily_request_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily request limit of {daily_request_limit} reached",
        )

    prompt = f"""Today's date is {today}.
Extract structured info from this input. Return ONLY valid JSON, no other text, no markdown formatting.
Input: "{request.text}"
Return JSON in this exact format:
{{
  "type": "task" or "reminder" or "note",
  "title": "a clean, short title",
  "due_date": "YYYY-MM-DD or null if no date mentioned"
}}
If a relative date is mentioned (e.g. "Friday", "tomorrow", "next week"), calculate the actual date based on today's date."""

    try:
        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {str(e)}")

    result_text = response.text.strip()
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]
        result_text = result_text.strip()

    try:
        parsed = json.loads(result_text)
    except json.JSONDecodeError:
        parsed = {"type": "task", "title": request.text, "due_date": None}

    save_usage_count(user_id, today, current_count + 1)

    return parsed


@app.get("/")
def health_check():
    return {"status": "backend is running"}