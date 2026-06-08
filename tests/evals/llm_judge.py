# tests/evals/llm_judge.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.llm import call_llm, parse_json_response

JUDGE_PROMPT = """
You are an eval judge for an autonomous analytics agent.
Evaluate the output against the specific property provided.

Return ONLY valid JSON:
{
  "pass": true or false,
  "score": 0.0 to 1.0,
  "reason": "one sentence explanation"
}

Be strict. Pass only if score >= 0.7.
"""


def judge(output: str, property_to_evaluate: str) -> dict:
    """Ask LLM to evaluate a semantic property of agent output."""
    try:
        raw = call_llm(
            system_prompt=JUDGE_PROMPT,
            user_message=f"OUTPUT:\n{output}\n\nPROPERTY:\n{property_to_evaluate}",
            temperature=0.1,
        )
        return parse_json_response(raw)
    except Exception as e:
        return {"pass": False, "score": 0.0, "reason": f"Judge error: {e}"}