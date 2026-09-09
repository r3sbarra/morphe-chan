#!/usr/bin/env python
"""import_analysis.py — Import analysis: dig down to imports + dependencies.

  1. EXTRACT imports from each file (per language)
  2. BUILD a dependency graph (file -> imports, import -> files)
  3. ADD import dimensions to the composite vector:
       IMP:<module>   — which modules are imported (dependency footprint)
       IMP_COUNT      — total imports
       IMP_UNIQUE     — unique modules
       DEPTH          — dependency depth (how deep the import tree goes)
  4. ENABLE digging down: given a file, show what it imports and what imports it

Dependency-free (stdlib only).
"""
import os
import re
import math
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Set

# ── Per-language import patterns ────────────────────────────────────────────
IMPORT_PATTERNS = {
    "python": [r"^\s*import\s+([\w.]+)", r"^\s*from\s+([\w.]+)\s+import"],
    "javascript": [r"^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
                   r"^\s*import\s+['\"]([^'\"]+)['\"]",
                   r"^\s*require\s*\(\s*['\"]([^'\"]+)['\"]"],
    "typescript": [r"^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
                   r"^\s*import\s+['\"]([^'\"]+)['\"]"],
    "java": [r"^\s*import\s+([\w.]+)"],
    "c": [r"^\s*#include\s*[<\"]([^>\"]+)[>\"]"],
    "cpp": [r"^\s*#include\s*[<\"]([^>\"]+)[>\"]"],
    "csharp": [r"^\s*using\s+([\w.]+)"],
    "go": [r"^\s*import\s*\(([^)]*)\)", r"^\s*import\s+['\"]([^'\"]+)['\"]"],
    "rust": [r"^\s*use\s+([\w:]+)"],
    "ruby": [r"^\s*require\s*['\"]([^'\"]+)['\"]", r"^\s*require_relative\s*['\"]([^'\"]+)['\"]"],
    "php": [r"^\s*(?:use|require|include)\s+([\w\\]+)"],
    "swift": [r"^\s*import\s+([\w.]+)"],
    "kotlin": [r"^\s*import\s+([\w.]+)"],
}

EXT = {
    "python": [".py"], "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"], "java": [".java"],
    "c": [".c", ".h"], "cpp": [".cpp", ".cc", ".hpp"],
    "csharp": [".cs"], "go": [".go"], "rust": [".rs"],
    "ruby": [".rb"], "php": [".php"], "swift": [".swift"],
    "kotlin": [".kt", ".kts"],
}
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target",
             "__pycache__", ".venv", "venv", "test", "tests", "spec", "specs",
             "examples", "docs", "benchmark", "benchmarks", "third_party",
             "third-party", "external", "deps", "assets", "static", "coverage",
             ".github", "bin", "obj", "out"}


def _lang_of(fn: str) -> str:
    for lang, exts in EXT.items():
        if any(fn.endswith(e) for e in exts):
            return lang
    return None


def extract_imports(code: str, lang: str) -> List[str]:
    """Extract imported modules from code."""
    imports = []
    patterns = IMPORT_PATTERNS.get(lang, [])
    for pat in patterns:
        for m in re.finditer(pat, code, re.MULTILINE):
            mod = m.group(1).strip()
            if mod and mod not in imports:
                imports.append(mod)
    return imports


def analyze_imports(root: Path, max_files: int = 500) -> Dict:
    """Analyze a project's imports: dependency graph + import stats."""
    file_imports = {}  # file -> [imports]
    import_files = defaultdict(list)  # module -> [files]
    import_count = 0
    unique_modules = set()
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            lang = _lang_of(fn)
            if not lang:
                continue
            fpath = Path(dirpath) / fn
            rel = str(fpath.relative_to(root))
            try:
                code = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            imports = extract_imports(code, lang)
            if imports:
                file_imports[rel] = imports
                for mod in imports:
                    import_files[mod].append(rel)
                    unique_modules.add(mod)
                    import_count += 1
            file_count += 1
            if file_count >= max_files:
                break
        if file_count >= max_files:
            break

    return {
        "file_imports": file_imports,
        "import_files": dict(import_files),
        "import_count": import_count,
        "unique_modules": len(unique_modules),
        "files_with_imports": len(file_imports),
        "total_files": file_count,
    }


def import_vector(root: Path, max_files: int = 500) -> Dict[str, float]:
    """Import dimensions for the composite vector."""
    res = analyze_imports(root, max_files)
    vec: Dict[str, float] = {}
    # top imported modules
    mod_count = Counter()
    for mods in res["file_imports"].values():
        for m in mods:
            mod_count[m] += 1
    total = max(1, res["import_count"])
    for mod, c in mod_count.most_common(10):
        vec[f"IMP:{mod}"] = c / total
    vec["IMP_COUNT"] = res["import_count"]
    vec["IMP_UNIQUE"] = res["unique_modules"]
    vec["IMP_FILES"] = res["files_with_imports"]
    return vec


def dig_imports(root: Path, target_file: str) -> Dict:
    """Dig down into a file's imports: what it imports + what imports it."""
    res = analyze_imports(root)
    imports = res["file_imports"].get(target_file, [])
    importers = [f for f, mods in res["file_imports"].items() if target_file in mods]
    return {
        "file": target_file,
        "imports": imports,
        "imported_by": importers,
    }


def dependency_depth(root: Path, max_files: int = 500) -> int:
    """Estimate the max dependency depth (how deep the import tree goes)."""
    res = analyze_imports(root, max_files)
    # BFS from files with no imports
    file_imports = res["file_imports"]
    # reverse: module -> files that import it
    import_files = res["import_files"]
    # depth of each file = 1 + max depth of its imports (if import is a local file)
    local_files = set(file_imports.keys())
    depth = {}
    for f in file_imports:
        depth[f] = _file_depth(f, file_imports, import_files, local_files, depth, set())
    return max(depth.values()) if depth else 0


def _file_depth(f, file_imports, import_files, local_files, depth, visiting):
    if f in depth:
        return depth[f]
    if f in visiting:
        return 0  # cycle
    visiting.add(f)
    max_d = 0
    for mod in file_imports.get(f, []):
        # is this import a local file?
        for lf in local_files:
            if lf.startswith(mod) or mod in lf:
                d = _file_depth(lf, file_imports, import_files, local_files, depth, visiting)
                max_d = max(max_d, d)
    depth[f] = 1 + max_d
    visiting.discard(f)
    return depth[f]


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("import os\nimport requests\nfrom utils import helper")
        (root / "utils.py").write_text("import json\nimport os\ndef helper():\n    return 1")
        (root / "app.js").write_text("import React from 'react'\nimport { useState } from 'react'")

        print("=== Import analysis ===")
        res = analyze_imports(root)
        print(f"imports: {res['import_count']}, unique: {res['unique_modules']}, files: {res['files_with_imports']}")
        for f, mods in res["file_imports"].items():
            print(f"  {f}: {mods}")
        print(f"dependency depth: {dependency_depth(root)}")
        print(f"import vector: {import_vector(root)}")
        print(f"dig main.py: {dig_imports(root, 'main.py')}")
