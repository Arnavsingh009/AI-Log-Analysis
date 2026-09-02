import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_stack_trace(service_name: str, message: str, stack_trace: str) -> dict:
    prompt = f"""You are an automated Site Reliability Engineer (SRE).
Analyze this error and return pure JSON with keys: 'root_cause', 'affected_component', 'severity', 'suggested_fix'.

Service: {service_name}
Error: {message}
Trace:
{stack_trace}
"""
    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ [AI ERROR]: {e}")
        return {
            "root_cause": f"Groq triage failed: {str(e)}",
            "affected_component": "Unknown",
            "severity": "CRITICAL",
            "suggested_fix": "Verify GROQ_API_KEY inside your .env file."
        }