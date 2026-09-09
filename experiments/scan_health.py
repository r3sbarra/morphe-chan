#!/usr/bin/env python
"""scan_health.py — Per-project health score.
- complexity (long functions) into a health score.
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

for proj in ["flask", "requests", "gson", "okhttp", "redis", "lodash",
             "express", "gin", "cobra", "libsodium"]:
    p = base / proj
    if not p.is_dir():
        continue
    total_lines = 0
    comments = 0
    long_fns = 0
    sec_signals = 0
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
            long_fns += sum(1 for m in re.finditer(r"(?:def|function|func|fun)\s+\w+\s*\(", code)
                            if code[m.start():m.start() + 2000].count("\n") > 30)
            if re.search(r"hashlib\.md5|hashlib\.sha1|password\s*=\s*[\"'][^\"']+[\"']|\beval\s*\(|SELECT.*\+.*\w+", code):
                sec_signals += 1

    comment_ratio = comments / total_lines if total_lines else 0
    health = comment_ratio * 10 - sec_signals * 0.5 - long_fns * 0.01
    print(f"{proj:12s} health={health:6.2f} comment_ratio={comment_ratio:.2f} "
          f"sec_signals={sec_signals:3d} long_fns={long_fns:4d}")
