#!/usr/bin/env python
"""derive_higher_order.py — Second-order dimensions from all derived info.
insights:

  RISK_ADJUSTED_COMPLEXITY = congestion * risk
  MAINTAINABILITY_RISK     = long_fns * coupling
  SECURITY_DEBT            = security_signals * code_size
  ARCH_FRAGILITY           = fan_in * coupling
  OVERALL_RISK             = risk + congestion + security_debt

These combine the first-order dimensions into actionable second-order metrics.
"""
import re
import os
from pathlib import Path

base = Path("/tmp/shape-projects")
SKIP = {"node_modules", ".git", "vendor", "dist", "build", "target",
        "__pycache__", ".venv", "venv", "test", "tests", "spec", "specs",
        "examples", "docs", "benchmark", "benchmarks", "third_party",
        "third-party", "external", "deps", "assets", "static", "coverage",
        ".github", "bin", "obj", "out"}
EXTS = {".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".go", ".rs",
        ".rb", ".php", ".swift", ".kt"}

results = {}
for proj in ["flask", "requests", "gson", "okhttp", "redis", "lodash",
             "express", "gin", "cobra", "libsodium"]:
    p = base / proj
    if not p.is_dir():
        continue
    total_lines = 0
    comments = 0
    long_fns = 0
    sec_signals = 0
    total_fns = 0
    for dirpath, dirnames, filenames in os.walk(p):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for fn in filenames:
            if not any(fn.endswith(e) for e in EXTS):
                continue
            try:
                code = (Path(dirpath) / fn).read_text(errors="replace")
            except Exception:
                continue
            if len(code) > 20000:
                continue
            lines = code.splitlines()
            total_lines += len(lines)
            comments += sum(1 for l in lines if l.strip().startswith("#") or l.strip().startswith("//"))
            total_fns += len(re.findall(r"(?:def|function|func|fun)\s+\w+\s*\(", code))
            long_fns += sum(1 for m in re.finditer(r"(?:def|function|func|fun)\s+\w+\s*\(", code)
                            if code[m.start():m.start() + 2000].count("\n") > 30)
            if re.search(r"hashlib\.md5|hashlib\.sha1|password\s*=\s*[\"'][^\"']+[\"']|\beval\s*\(|SELECT.*\+.*\w+", code):
                sec_signals += 1

    # first-order dimensions
    comment_ratio = comments / total_lines if total_lines else 0
    coupling = min(1.0, total_fns / 100.0)  # normalized coupling proxy
    congestion = coupling + min(1.0, long_fns / 100.0) + min(1.0, sec_signals)
    risk = sec_signals * 0.5 + (1 - comment_ratio) * 0.3

    # second-order dimensions
    risk_adj_complexity = congestion * risk
    maintainability_risk = long_fns * coupling
    security_debt = sec_signals * (total_lines / 1000.0)
    arch_fragility = coupling * min(1.0, long_fns / 50.0)
    overall_risk = risk + congestion * 0.5 + security_debt * 0.1

    results[proj] = {
        "risk_adj_complexity": round(risk_adj_complexity, 3),
        "maintainability_risk": round(maintainability_risk, 1),
        "security_debt": round(security_debt, 2),
        "arch_fragility": round(arch_fragility, 3),
        "overall_risk": round(overall_risk, 3),
    }

print("=== Higher-order dimensions per project ===")
print(f"{'proj':12s} {'risk_adj':>9s} {'maint_risk':>10s} {'sec_debt':>8s} {'fragility':>9s} {'overall':>8s}")
for proj, r in sorted(results.items(), key=lambda x: -x[1]["overall_risk"]):
    print(f"{proj:12s} {r['risk_adj_complexity']:>9.3f} {r['maintainability_risk']:>10.1f} "
          f"{r['security_debt']:>8.2f} {r['arch_fragility']:>9.3f} {r['overall_risk']:>8.3f}")
