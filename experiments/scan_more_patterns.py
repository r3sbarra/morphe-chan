#!/usr/bin/env python
"""scan_more_patterns.py — Scan for more detectable patterns.
anti-patterns, code smells, and architectural patterns across projects.
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

patterns = {
    # Security anti-patterns
    "hardcoded_secret": r"password\s*=\s*[\"'][^\"']+[\"']|api_key\s*=\s*[\"'][^\"']+[\"']|secret\s*=\s*[\"'][^\"']+[\"']",
    "unsafe_eval": r"\beval\s*\(|\bexec\s*\(|pickle\.loads|yaml\.load\s*\(",
    "sql_concat": r"SELECT.*\+.*\w+|execute\s*\([^)]*\+",
    "shell_injection": r"os\.system\s*\([^)]*\+|system\s*\([^)]*\+|subprocess.*shell\s*=\s*True",
    "weak_crypto": r"hashlib\.md5|hashlib\.sha1|md5\s*\(|sha1\s*\(|random\.random|random\.randint",
    "path_traversal": r"open\s*\([^)]*\+|fopen\s*\([^)]*\+|os\.path\.join\s*\([^)]*\+",
    # Performance anti-patterns
    "nested_loop": r"for\s+.*:\s*\n\s*for\s+",
    "string_concat_loop": r"for\s+.*:\s*\n\s*\w+\s*=\s*\w+\s*\+",
    "len_in_loop": r"for\s+.*:\s*\n\s*\w+\s*\+=\s*len\s*\(",
    "redundant_compute": r"for\s+.*:\s*\n\s*\w+\s*\+=\s*(?:len|sum|count)\s*\(",
    "deep_nesting": r"if\s+.*:\s*\n\s*if\s+.*:\s*\n\s*if\s+",
    # Code smells
    "magic_number": r"=\s*\d{4,}",
    "long_params": r"def\s+\w+\([^)]{60,}\)",
    "global_mutation": r"^\s*global\s+\w+|^\s*nonlocal\s+\w+",
    # Architectural
    "mvc": r"class\s+\w+Controller|class\s+\w+View|class\s+\w+Model",
    "microservice": r"@app\.route|@RequestMapping|@GetMapping|router\.(get|post|put|delete)",
    "event_driven": r"\.emit\s*\(|\.on\s*\(|EventEmitter|publish\s*\(|subscribe\s*\(",
    "plugin_arch": r"register_plugin|load_plugin|PluginManager|\.register\s*\(",
    "dependency_injection": r"@Inject|@Autowired|inject\s*\(|Container\s*\(",
    "middleware": r"middleware|use\s*\(|app\.use|\.before_request|\.after_request",
    "config_management": r"config\s*=|ConfigParser|\.env|os\.environ|getenv",
    "error_handling": r"try\s*:|except\s+|catch\s*\(|raise\s+|throw\s+",
    "logging_framework": r"logger\s*=|logging\.|log\.info|log\.error|Logger\s*\(",
    "testing": r"def\s+test_\w+|@pytest|@Test|it\s*\(|describe\s*\(",
}

detected = Counter()
for proj in ["flask", "requests", "gson", "okhttp", "redis", "lodash",
             "express", "gin", "cobra", "libsodium"]:
    p = base / proj
    if not p.is_dir():
        continue
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
            for pat_name, pat in patterns.items():
                if re.search(pat, code, re.IGNORECASE):
                    detected[pat_name] += 1

print("=== MORE detectable patterns across projects ===")
for pat, count in detected.most_common():
    print(f"  {pat:24s} {count}")
