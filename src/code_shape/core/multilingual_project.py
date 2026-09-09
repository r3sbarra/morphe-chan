#!/usr/bin/env python
"""multilingual_project.py — Multi-lingual project shape analysis.
languages (e.g. Python backend + JS frontend + SQL + HTML).

For each language in a project:
  1. Detect the language (by file extension)
  2. Decompose its files into shapes (code-agnostic core)
  3. Aggregate into a per-language shape

Then build a COMPOSITE multi-lingual project shape:
  - per-language shapes (what each language contributes)
  - language distribution (how much of each)
  - cross-language structure (which languages coexist)

Dependency-free (stdlib only).
"""
import os
import math
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List

from code_shape.core.code_shape_core import recursive_shape, shape as get_shape, get_adapter, list_languages

# language -> file extensions
EXT = {
    "python": [".py"],
    "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"],
    "java": [".java"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".hpp"],
    "csharp": [".cs"],
    "go": [".go"],
    "rust": [".rs"],
    "ruby": [".rb"],
    "php": [".php"],
    "swift": [".swift"],
    "kotlin": [".kt", ".kts"],
    "sql": [".sql"],
    "html": [".html", ".htm"],
    "css": [".css"],
    "shell": [".sh", ".bash"],
    "json": [".json"],
    "yaml": [".yaml", ".yml"],
    "markdown": [".md"],
}

SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target",
             "__pycache__", ".venv", "venv", "test", "tests", "spec", "specs",
             "examples", "docs", "benchmark", "benchmarks", "third_party",
             "third-party", "external", "deps", "assets", "static", "coverage",
             ".github", "bin", "obj", "out", "coverage", "migrations"}


def detect_languages(root: Path) -> Dict[str, int]:
    """Detect all languages in a project. Returns {lang: file_count}."""
    counts = Counter()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            for lang, exts in EXT.items():
                if any(fn.endswith(e) for e in exts):
                    counts[lang] += 1
                    break
    return dict(counts)


def analyze_language(root: Path, lang: str, max_files: int = 200) -> Dict:
    """Decompose a language's files in a project into a per-language shape."""
    exts = EXT.get(lang, [])
    total = Counter()
    func_count = 0
    file_count = 0
    file_shapes = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not any(fn.endswith(e) for e in exts):
                continue
            fpath = Path(dirpath) / fn
            try:
                code = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if len(code) > 20000:
                continue
            counts = recursive_shape(code, lang)
            for k, v in counts.items():
                total[k] += v
            adapter = get_adapter(code, lang)
            func_count += len(adapter.extract_functions(code))
            file_shapes.append(get_shape(code, lang))
            file_count += 1
            if file_count >= max_files:
                break
        if file_count >= max_files:
            break
    ranked = sorted(total.items(), key=lambda kv: -kv[1])
    top = [p for p, c in ranked if c > 0][:6]
    return {
        "files": file_count,
        "functions": func_count,
        "shape": ">".join(top) if top else "EMPTY",
        "primitives": {k: v for k, v in ranked if v > 0},
    }


def analyze_project(root: Path) -> Dict:
    """Analyze a multi-lingual project: per-language shapes + composite."""
    langs = detect_languages(root)
    per_lang = {}
    for lang, count in sorted(langs.items(), key=lambda kv: -kv[1]):
        if count == 0:
            continue
        per_lang[lang] = analyze_language(root, lang)

    # composite project shape: weighted by file count
    total_files = sum(langs.values())
    composite = Counter()
    for lang, info in per_lang.items():
        weight = info["files"] / total_files if total_files else 0
        for prim, c in info["primitives"].items():
            composite[prim] += c * weight
    ranked = sorted(composite.items(), key=lambda kv: -kv[1])
    top = [p for p, c in ranked if c > 0][:6]

    return {
        "languages": langs,
        "total_files": total_files,
        "per_language": per_lang,
        "composite_shape": ">".join(top) if top else "EMPTY",
        "language_distribution": {k: round(v / total_files, 3) for k, v in langs.items()},
    }


def project_summary(root: Path) -> str:
    """Human-readable multi-lingual project summary."""
    res = analyze_project(root)
    lines = [f"Project: {root.name} ({res['total_files']} files)"]
    for lang, count in sorted(res["languages"].items(), key=lambda kv: -kv[1]):
        info = res["per_language"].get(lang, {})
        lines.append(f"  {lang:12s} {count:4d} files, {info.get('functions', 0):5d} fns, shape={info.get('shape', 'EMPTY')}")
    lines.append(f"  COMPOSITE: {res['composite_shape']}")
    return "\n".join(lines)


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile
    # Build a synthetic multi-lingual project
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.py").write_text("def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total")
        (root / "server.js").write_text("function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}")
        (root / "db.sql").write_text("SELECT * FROM users WHERE name = 'x';\nINSERT INTO logs VALUES (1);")
        (root / "index.html").write_text("<html><body><div>Hello</div></body></html>")
        (root / "style.css").write_text("body { color: red; }")
        (root / "deploy.sh").write_text("#!/bin/bash\necho 'deploying'\nls -la")

        print("=== Multi-lingual project analysis ===")
        print(project_summary(root))
