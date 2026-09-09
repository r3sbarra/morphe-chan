#!/usr/bin/env python
"""decompose_projects.py — Run shape decomposition on entire GitHub projects.
into its shape (via the code-agnostic core), and aggregates into a project-level
composite shape. Verifies the shape model can decompose WHOLE projects.

Usage: python3 decompose_projects.py /tmp/shape-projects
"""
import sys
import os
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from code_shape.core.code_shape_core import recursive_shape, shape, get_adapter, list_languages

# language -> file extensions
EXT = {
    "python": [".py"],
    "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"],
    "java": [".java"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".hpp", ".h"],
    "csharp": [".cs"],
    "go": [".go"],
    "rust": [".rs"],
    "ruby": [".rb"],
    "php": [".php"],
    "swift": [".swift"],
    "kotlin": [".kt", ".kts"],
}

# dirs to skip (vendored, build, test fixtures, node_modules)
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target",
             "__pycache__", ".venv", "venv", "test", "tests", "spec", "specs",
             "examples", "docs", "benchmark", "benchmarks", "third_party",
             "third-party", "external", "deps", "lib", "assets", "static",
             "coverage", ".github", "bin", "obj", "out"}


def project_files(root: Path, lang: str) -> list:
    """Find source files for a language in a project, skipping vendored dirs."""
    exts = EXT.get(lang, [])
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune skip dirs
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if any(fn.endswith(e) for e in exts):
                files.append(Path(dirpath) / fn)
    return files


def decompose_project(root: Path, lang: str) -> dict:
    """Decompose an entire project into its composite shape."""
    files = project_files(root, lang)
    if not files:
        return {"files": 0, "functions": 0, "shape": "EMPTY", "primitives": {}}

    total = Counter()
    func_count = 0
    file_shapes = []
    for f in files[:200]:  # cap at 200 files per project for speed
        try:
            code = f.read_text(encoding="utf-8", errors="replace")
            counts = recursive_shape(code, lang)
            for k, v in counts.items():
                total[k] += v
            # count functions
            adapter = get_adapter(code, lang)
            func_count += len(adapter.extract_functions(code))
            file_shapes.append(shape(code, lang))
        except Exception:
            continue

    # project shape = dominant primitives across all files
    ranked = sorted(total.items(), key=lambda kv: -kv[1])
    top = [p for p, c in ranked if c > 0][:6]
    return {
        "files": len(files),
        "functions": func_count,
        "shape": ">".join(top) if top else "EMPTY",
        "primitives": {k: v for k, v in ranked if v > 0},
    }


def main():
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/shape-projects")
    print(f"=== Project Shape Decomposition ({base}) ===")
    print(f"{'project':16s} {'lang':10s} {'files':>6s} {'fns':>6s} {'shape':40s}")
    results = {}
    for proj_dir in sorted(base.iterdir()):
        if not proj_dir.is_dir():
            continue
        # detect the project's language by file presence (most files wins)
        lang = None
        best_count = 0
        for l in list_languages():
            n = len(project_files(proj_dir, l))
            if n > best_count:
                best_count = n
                lang = l
        if not lang or best_count == 0:
            continue
        res = decompose_project(proj_dir, lang)
        results[proj_dir.name] = (lang, res)
        print(f"{proj_dir.name:16s} {lang:10s} {res['files']:>6d} {res['functions']:>6d} {res['shape']:40s}")

    print("\n=== Summary ===")
    langs = {}
    for name, (lang, res) in results.items():
        langs.setdefault(lang, []).append(res)
    for lang, ress in langs.items():
        total_files = sum(r["files"] for r in ress)
        total_fns = sum(r["functions"] for r in ress)
        shapes = [r["shape"] for r in ress]
        print(f"  {lang:10s}: {len(ress)} projects, {total_files} files, {total_fns} functions")
        print(f"    shapes: {shapes}")


if __name__ == "__main__":
    main()
