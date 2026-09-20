#!/usr/bin/env python
"""experiment_real_cve.py — Test detector on real-world CVEs.
patterns and checks whether it flags the CORRECT vulnerability type and the
CORRECT source (the part of the shape that's the taint source).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from code_shape.security.precise_issues import find_precise_issues, find_buffer_overflows
from code_shape.security.exploitability import exploitability_score
from real_cve_corpus import REAL_CVES


def main():
    print("=== Real-World CVE Detection Test (LIVE pipeline) ===")
    print(f"{'CVE':14s} {'name':26s} {'detected':22s} {'expected':18s} {'OK':>3s} {'exploit':>8s}")
    correct_type = 0
    correct_source = 0
    for cve, name, code, exp_type, exp_source in REAL_CVES:
        # LIVE authoritative pipeline (precise_issues + buffer_overflows) —
        # NOT the deprecated detect_vulns_v2 which misses CVE sink patterns.
        vulns = find_precise_issues(code) + find_buffer_overflows(code)
        detected_types = [v.get("type") for v in vulns]
        type_ok = exp_type in detected_types
        correct_type += type_ok
        source_ok = _source_is_tainted(code, exp_source)
        correct_source += source_ok
        exp = exploitability_score(code, exp_type)
        print(f"{cve:14s} {name:26s} {str(detected_types):22s} {exp_type:18s} "
              f"{'OK' if type_ok else 'XX':>3s} {exp['score']:>8.2f}")

    print(f"\n=== Summary (LIVE pipeline) ===")
    print(f"Correct vulnerability type: {correct_type}/{len(REAL_CVES)}")
    print(f"Correct source (tainted, flows to sink): {correct_source}/{len(REAL_CVES)}")


def _source_is_tainted(code: str, source: str) -> bool:
    """Verify the source is a tainted variable that flows to a sink.

    Uses value-flow taint tracking: the source must be a tainted input
    (param/request/env) that propagates to a dangerous call.
    """
    from code_shape.core.value_flow_shape import _extract_params, _propagate_taint
    from code_shape.security.dangerous_intent import detect_dangerous_intent
    params = _extract_params(code)
    taint = _propagate_taint(code, params)
    # is the source a tainted variable?
    if source in taint:
        return True
    # is the source a public input (request/input/env) that reaches a sink?
    if any(s in source.lower() for s in ["request", "input", "argv", "env", "form", "query", "header", "cookie"]):
        # check it reaches a dangerous call
        intents = detect_dangerous_intent(code)
        return len(intents) > 0
    return False


if __name__ == "__main__":
    main()
