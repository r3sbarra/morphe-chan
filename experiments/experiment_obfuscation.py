#!/usr/bin/env python
"""experiment_obfuscation.py — Obfuscation/renaming resistance test.
functions renamed to look safe.

Cases:
  1. RENAMED FUNCTION — a dangerous sink wrapped in a safe-sounding function
     name (e.g. `def sanitize(x): os.system(x)`) — the SINK is still dangerous.
  2. OBFUSCATED SINK — the dangerous function is aliased/renamed
     (e.g. `s = os.system; s(cmd)`) — the sink is hidden.
  3. SAFE CODE — genuinely safe code should NOT be flagged.
  4. DECLARATION vs USAGE — a function named `exec` (declaration) vs calling it.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from code_shape.security.precise_issues import find_precise_issues, find_buffer_overflows, issue_summary

# (name, code, should_flag)
CASES = [
    # Renamed function wrapping a dangerous sink — SHOULD flag (sink is dangerous)
    ("renamed-cmd", "def sanitize_input(cmd):\n    return os.system(cmd)", True),
    ("renamed-eval", "def safe_parse(data):\n    return eval(data)", True),
    ("renamed-sql", "def clean_query(name):\n    return db.execute('SELECT * FROM users WHERE name = ' + name)", True),
    # Obfuscated sink (aliased) — hard to detect, honest test
    ("aliased-system", "import os\ns = os.system\ns(cmd)", True),
    # Safe code — should NOT flag
    ("safe-param", "def get_user(name):\n    return db.execute('SELECT * FROM users WHERE name = ?', (name,))", False),
    ("safe-escape", "def render(name):\n    safe = html.escape(name)\n    return '<div>' + safe + '</div>'", False),
    # Declaration vs usage — declaration should NOT flag
    ("decl-exec", "def exec(cmd):\n    return cmd", False),
    ("decl-eval", "def eval(expr):\n    return expr", False),
]


def main():
    print("=== Obfuscation / Renaming Resistance Test ===")
    print(f"{'case':18s} {'flagged':8s} {'expected':9s} {'OK':>3s} {'summary'}")
    correct = 0
    for name, code, should_flag in CASES:
        issues = find_precise_issues(code) + find_buffer_overflows(code)
        flagged = len(issues) > 0
        ok = flagged == should_flag
        correct += ok
        print(f"{name:18s} {str(flagged):8s} {str(should_flag):9s} {'OK' if ok else 'XX':>3s} {issue_summary(code)}")
    print(f"\nAccuracy: {correct}/{len(CASES)}")


if __name__ == "__main__":
    main()
