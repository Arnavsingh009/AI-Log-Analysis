import os
import json
from dotenv import load_dotenv
from groq import Groq

# Load environment variables from .env file
load_dotenv()

# Retrieve key from environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set. Please add it to your .env file.")

client = Groq(api_key=GROQ_API_KEY)

def analyze_stack_trace(service_name: str, message: str, stack_trace: str) -> dict:
    """Sends raw stack trace to LLM and returns structured RCA."""
    if not stack_trace:
        return {"summary": "No stack trace provided", "suggested_fix": "N/A"}

    prompt = f"""
You are an expert Site Reliability Engineer (SRE). Analyze this production crash:
- Service: {service_name}
- Error Message: {message}
- Stack Trace:
{stack_trace}

Return your response strictly in the following JSON format:
{{
  "root_cause": "Plain English summary of why it broke (1-2 sentences)",
  "affected_component": "File name and line number if visible, or failing subsystem",
  "severity": "CRITICAL, HIGH, or MEDIUM",
  "suggested_fix": "Clear, actionable step to fix or prevent this issue"
}}
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        return {"error": f"AI Triage Failed: {str(e)}"}