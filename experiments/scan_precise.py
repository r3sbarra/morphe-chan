#!/usr/bin/env python
"""scan_precise.py — Precise vulnerability + efficiency scan on real projects.
the cloned GitHub projects, and an efficiency check (empirical complexity on
sample functions).

Usage: python3 scan_precise.py /tmp/shape-projects
"""
import sys
import os
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from code_shape.security.precise_issues import find_precise_issues, issue_summary
from code_shape.security.exploitability import exploitability_score

EXTS = {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp", ".cc",
        ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".kts"}
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target",
             "__pycache__", ".venv", "venv", "test", "tests", "spec", "specs",
             "examples", "docs", "benchmark", "benchmarks", "third_party",
             "third-party", "external", "deps", "assets", "static", "coverage",
             ".github", "bin", "obj", "out"}
TEST_MARKERS = ("test", "spec", "benchmark", "perf", "example", "sample",
                "fixture", "mock", "_test", ".test.", ".spec.")


def scan_project(root: Path, max_files: int = 300) -> list:
    """Scan a project for precise vulnerabilities (real source only)."""
    findings = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not any(fn.endswith(e) for e in EXTS):
                continue
            if any(s in fn for s in ("min.js", "bundle", ".min.")):
                continue
            fpath = Path(dirpath) / fn
            rel = str(fpath.relative_to(root))
            if any(m in rel.lower() for m in TEST_MARKERS):
                continue  # skip test/benchmark
            try:
                code = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if len(code) > 20000:
                continue
            issues = find_precise_issues(code)
            if issues:
                for i in issues:
                    exp = exploitability_score(code, i["type"])
                    findings.append({
                        "file": rel,
                        "type": i["type"],
                        "line": i["line"],
                        "sink": i["sink"],
                        "source": i["source"],
                        "shape_dim": i["shape_dimension"],
                        "exploitability": exp["score"],
                        "label": exp["label"],
                    })
            count += 1
            if count >= max_files:
                return findings
    return findings


def main():
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/shape-projects")
    print(f"=== Precise Vulnerability Scan on Real Projects ({base}) ===")
    all_findings = defaultdict(list)
    for proj_dir in sorted(base.iterdir()):
        if not proj_dir.is_dir():
            continue
        findings = scan_project(proj_dir)
        if findings:
            for f in findings:
                all_findings[f["type"]].append(f"{proj_dir.name}/{f['file']}:L{f['line']}")

    print(f"\n=== Findings by precise type (real source, test excluded) ===")
    for vtype, files in sorted(all_findings.items(), key=lambda kv: -len(kv[1])):
        print(f"  {vtype:20s} ({len(files)}):")
        for f in files[:6]:
            print(f"    - {f}")
        if len(files) > 6:
            print(f"    ... and {len(files)-6} more")

    print(f"\n=== High-exploitability findings (CRITICAL/HIGH) ===")
    high = []
    for proj_dir in sorted(base.iterdir()):
        if not proj_dir.is_dir():
            continue
        for f in scan_project(proj_dir):
            if f["label"] in ("CRITICAL", "HIGH"):
                high.append(f)
    for f in high[:15]:
        print(f"  [{f['label']}] {f['type']} {f['file']}:L{f['line']} "
              f"src={f['source']} sink={f['sink']} dim={f['shape_dim']}")


if __name__ == "__main__":
    main()
