"""PostToolUse nudge: after editing a test file, remind the agent to link the new
test to its requirement in AQA. Non-blocking (always exit 0) — just a reminder.
Reads the hook's JSON event on stdin."""

import json
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    path = (data.get("tool_input") or {}).get("file_path", "") or ""
    if "/tests/" in path or path.startswith("tests/"):
        print(
            "AQA: if this test closes a requirement, call "
            "link_coverage(req_id, [case_id]) so get_coverage_gaps reflects it."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
