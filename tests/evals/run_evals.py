# tests/evals/run_evals.py

"""
Run all evals and produce a summary report.

Usage:
  uv run python tests/evals/run_evals.py           # all evals
  uv run python tests/evals/run_evals.py --fast    # structural only
  uv run python tests/evals/run_evals.py --slow    # all including LLM
"""

import sys
import subprocess
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def run_evals(include_slow: bool = False):
    print("\n" + "="*60)
    print("  METRIC WATCHDOG — EVAL HARNESS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode: {'full (including LLM calls)' if include_slow else 'fast (structural only)'}")
    print("="*60)

    cmd = ["uv", "run", "pytest", "tests/evals/", "-v",
           "--tb=short", "--no-header",
           "--json-report", "--json-report-file=tests/evals/last_run.json"]

    if not include_slow:
        cmd.extend(["-m", "not slow"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:300])

    # Summary
    try:
        with open("tests/evals/last_run.json") as f:
            report = json.load(f)
        summary = report.get("summary", {})
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total", 0)
        duration = report.get("duration", 0)

        print("\n" + "="*60)
        print("  EVAL SUMMARY")
        print("="*60)
        print(f"  Passed:   {passed}/{total}")
        print(f"  Failed:   {failed}/{total}")
        print(f"  Duration: {duration:.1f}s")
        print(f"  Score:    {passed/total*100:.0f}%" if total > 0 else "  Score: N/A")
        print("\n  ✅ ALL PASSING" if failed == 0 else f"\n  ❌ {failed} FAILING")
        print("="*60 + "\n")
    except FileNotFoundError:
        print("Install pytest-json-report: uv add pytest-json-report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slow", action="store_true",
                        help="Include slow LLM-based evals")
    args = parser.parse_args()
    run_evals(include_slow=args.slow)