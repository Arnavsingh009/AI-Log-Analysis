import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_groq_client():
    key = os.getenv("GROQ_API_KEY")
    if not key or key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY is not configured in .env")
    return Groq(api_key=key)

def analyze_stack_trace(service_name: str, message: str, stack_trace: str) -> dict:
    if not stack_trace:
        return {"root_cause": "No stack trace provided", "suggested_fix": "N/A", "severity": "LOW"}

    prompt = f"""
You are an expert Site Reliability Engineer (SRE). Analyze this production crash:
- Service: {service_name}
- Error Message: {message}
- Stack Trace:
{stack_trace}

Return your response strictly in valid JSON with these exact keys:
{{
  "root_cause": "Plain English summary of why it broke (1-2 sentences)",
  "affected_component": "File name and line number if visible, or failing subsystem",
  "severity": "CRITICAL",
  "suggested_fix": "Clear, actionable step to fix or prevent this issue"
}}
"""
    try:
        client = get_groq_client()
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",  # Updated to fast, universally available Groq model
            response_format={"type": "json_object"}
        )
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ [AI ERROR]: {e}")
        return {
            "root_cause": f"AI Diagnostic Failed: {str(e)}",
            "affected_component": "N/A",
            "severity": "HIGH",
            "suggested_fix": "Verify GROQ_API_KEY in .env or check network connectivity."
        }