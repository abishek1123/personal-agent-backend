from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv
from datetime import date
import os
import json

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()


class ParseRequest(BaseModel):
    text: str


@app.post("/parse-input")
def parse_input(request: ParseRequest):
    today = date.today().isoformat()

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

    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
    )
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

    return parsed


@app.get("/")
def health_check():
    return {"status": "backend is running"}