#!/usr/bin/env python
"""scan_security_posture.py — Security posture per project.
"""
import re
import os
from pathlib import Path
from collections import Counter

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
    signals = Counter()
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
            if re.search(r"hashlib\.md5|hashlib\.sha1|md5\s*\(|sha1\s*\(", code):
                signals["weak_crypto"] += 1
            if re.search(r"password\s*=\s*[\"'][^\"']+[\"']|api_key\s*=\s*[\"'][^\"']+[\"']", code):
                signals["hardcoded_secret"] += 1
            if re.search(r"\beval\s*\(|\bexec\s*\(|pickle\.loads", code):
                signals["unsafe_eval"] += 1
            if re.search(r"SELECT.*\+.*\w+|execute\s*\([^)]*\+", code):
                signals["sql_concat"] += 1
            if re.search(r"os\.system\s*\([^)]*\+|subprocess.*shell\s*=\s*True", code):
                signals["shell_injection"] += 1
            if re.search(r"open\s*\([^)]*\+|os\.path\.join\s*\([^)]*\+", code):
                signals["path_traversal"] += 1
            if re.search(r"random\.random|random\.randint", code):
                signals["insecure_random"] += 1

    total = sum(signals.values())
    print(f"{proj:12s} security_signals={total:3d} {dict(signals)}")
