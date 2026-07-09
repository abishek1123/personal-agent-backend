from fastapi import FastAPI
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import date
import os
import json

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-flash-lite-latest")

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

    response = model.generate_content(prompt)
    result_text = response.text.strip()

    # Gemini sometimes wraps JSON in markdown code blocks - strip those
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