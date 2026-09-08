import os
import json
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def analyze_stack_trace(service_name: str, message: str, stack_trace: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print(" [AI ERROR]: GROQ_API_KEY is missing from environment variables.")
        return {
            "root_cause": "Missing GROQ_API_KEY in .env",
            "affected_component": service_name,
            "severity": "HIGH",
            "suggested_fix": "Add GROQ_API_KEY to your root .env file."
        }

    client = Groq(api_key=api_key)

    prompt = f"""You are an automated Site Reliability Engineer (SRE).
Analyze this system crash and output ONLY valid JSON.
Do not wrap in markdown tags or backticks.

Expected JSON format:
{{
  "root_cause": "1-sentence explanation of failure",
  "affected_component": "Component or library name",
  "severity": "CRITICAL",
  "suggested_fix": "Specific technical remediation steps"
}}

Service: {service_name}
Error: {message}
Stack Trace:
{stack_trace}
"""

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You return strictly valid JSON objects only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        raw_text = completion.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        clean_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        clean_text = re.sub(r"\s*```$", "", clean_text).strip()

        return json.loads(clean_text)

    except Exception as exc:
        print(f"[AI ERROR in ai_service.py]: {repr(exc)}")
        return {
            "root_cause": f"Analysis encountered an error: {str(exc)[:120]}",
            "affected_component": service_name,
            "severity": "HIGH",
            "suggested_fix": "Inspect terminal logs for Groq API response."
        }