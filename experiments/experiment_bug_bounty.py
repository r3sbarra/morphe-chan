#!/usr/bin/env python
"""experiment_bug_bounty.py — Expanded bug-bounty detection test.
intent + sinks) on the expanded bug-bounty corpus and measures precision/recall.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from code_shape.security.precise_issues import find_precise_issues, find_buffer_overflows
from code_shape.security.dangerous_intent import detect_dangerous_intent
from bug_bounty_corpus import CORPUS


def detect(code: str) -> list:
    """Full detection stack."""
    issues = find_precise_issues(code) + find_buffer_overflows(code)
    intents = detect_dangerous_intent(code)
    types = [i["type"] for i in issues]
    # intent categories as additional signal
    for d in intents:
        cat = d["category"]
        if cat == "CODE_EXEC" and "EVAL_USE" not in types:
            types.append("EVAL_USE")
        elif cat == "SQL" and "SQL_INJECTION" not in types:
            types.append("SQL_INJECTION")
        elif cat == "FILE" and "PATH_TRAVERSAL" not in types:
            types.append("PATH_TRAVERSAL")
        elif cat == "RENDER" and "XSS" not in types:
            types.append("XSS")
        elif cat == "DESERIALIZE" and "DESERIALIZATION" not in types:
            types.append("DESERIALIZATION")
    return types


def main():
    print("=== Expanded Bug-Bounty Detection Test ===")
    print(f"Corpus: {len(CORPUS)} pairs ({len([c for c in CORPUS if c[2]])} vuln, "
          f"{len([c for c in CORPUS if not c[2]])} clean)\n")
    print(f"{'name':24s} {'vuln':>5s} {'clean':>5s} {'OK':>3s}")
    tp = fp = fn = tn = 0
    for name, cwe, v, c, vt in CORPUS:
        vd = len(detect(v)) > 0
        cd = len(detect(c)) > 0
        ok = vd and not cd
        if vd and not cd: tp += 1
        elif vd and cd: fp += 1
        elif not vd and not cd: fn += 1
        else: tn += 1
        print(f"{name:24s} {str(vd):>5s} {str(cd):>5s} {'OK' if ok else 'XX':>3s}")

    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    print(f"\nPrecision={prec:.2f} Recall={rec:.2f} F1={f1:.2f} ({tp}TP {fp}FP {fn}FN {tn}TN)")


if __name__ == "__main__":
    main()
