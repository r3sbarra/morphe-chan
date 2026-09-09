#!/usr/bin/env python
"""composite_vector.py — Full composite shape vector of entire projects.
project, capturing ALL dimensions:

  LANG:<lang>      — language distribution (which languages, how much)
  PRIM:<primitive> — primitive distribution (intent/structure across all code)
  FUNC             — function count
  CONN             — call-graph connections (function calls)
  FLOW:<op>        — value-flow transforms (data movement)
  EFF:<dim>        — efficiency (complexity, loops, threading)
  SINK:<cat>       — dangerous sinks present
  HARD:<type>      — hardcoded values (secrets, shell cmds)

The composite vector is the normalized concatenation of all these dimensions,
giving a complete geometric fingerprint of the whole project.

Dependency-free (stdlib only).
"""
import os
import math
from pathlib import Path
from collections import Counter
from typing import Dict

from code_shape.core.code_shape_core import recursive_shape, get_adapter
from code_shape.analysis.efficiency_shape import efficiency_vector
from code_shape.core.value_flow_shape import value_flow_shape
from code_shape.security.semantic_sinks import detect_sinks
from code_shape.security.intent_sinks import detect_hardcoded
from code_shape.core.import_analysis import import_vector, dependency_depth

EXT = {
    "python": [".py"], "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"], "java": [".java"],
    "c": [".c", ".h"], "cpp": [".cpp", ".cc", ".hpp"],
    "csharp": [".cs"], "go": [".go"], "rust": [".rs"],
    "ruby": [".rb"], "php": [".php"], "swift": [".swift"],
    "kotlin": [".kt", ".kts"], "sql": [".sql"], "html": [".html"],
    "css": [".css"], "shell": [".sh"], "json": [".json"],
    "yaml": [".yaml", ".yml"], "markdown": [".md"],
}
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target",
             "__pycache__", ".venv", "venv", "test", "tests", "spec", "specs",
             "examples", "docs", "benchmark", "benchmarks", "third_party",
             "third-party", "external", "deps", "assets", "static", "coverage",
             ".github", "bin", "obj", "out", "migrations"}


def _lang_of(fn: str) -> str:
    for lang, exts in EXT.items():
        if any(fn.endswith(e) for e in exts):
            return lang
    return None


def composite_vector(root: Path, max_files: int = 500) -> Dict[str, float]:
    """Form the full composite shape vector of an entire project."""
    vec: Dict[str, float] = {}
    lang_count = Counter()
    prim_count = Counter()
    flow_count = Counter()
    eff_count = Counter()
    sink_count = Counter()
    hard_count = Counter()
    func_count = 0
    conn_count = 0
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            lang = _lang_of(fn)
            if not lang:
                continue
            fpath = Path(dirpath) / fn
            try:
                code = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if len(code) > 20000:
                continue
            lang_count[lang] += 1
            file_count += 1

            # primitives (intent/structure)
            counts = recursive_shape(code, lang)
            for k, v in counts.items():
                prim_count[k] += v
            # functions + connections
            adapter = get_adapter(code, lang)
            funcs = adapter.extract_functions(code)
            func_count += len(funcs)
            for name, body in funcs.items():
                conn_count += len(adapter.extract_calls(body))
            # value flow
            vf = value_flow_shape(code)
            for k, v in vf.items():
                if k.startswith("FLOW:"):
                    flow_count[k[5:]] += 1
            # efficiency
            eff = efficiency_vector(code)
            for k, v in eff.items():
                eff_count[k] += v
            # sinks
            sinks = detect_sinks(code)
            for s in sinks:
                sink_count[s["category"]] += 1
            # hardcoded
            hard = detect_hardcoded(code)
            for h in hard:
                hard_count[h["type"]] += 1

            if file_count >= max_files:
                break
        if file_count >= max_files:
            break

    # build the vector
    total_files = max(1, file_count)
    for lang, c in lang_count.items():
        vec[f"LANG:{lang}"] = c / total_files
    for prim, c in prim_count.items():
        vec[f"PRIM:{prim}"] = c
    vec["FUNC"] = func_count
    vec["CONN"] = conn_count
    for op, c in flow_count.items():
        vec[f"FLOW:{op}"] = c
    for dim, c in eff_count.items():
        vec[f"EFF:{dim}"] = c
    for cat, c in sink_count.items():
        vec[f"SINK:{cat}"] = c
    for htype, c in hard_count.items():
        vec[f"HARD:{htype}"] = c

    # imports (dependency footprint)
    imp = import_vector(root, max_files)
    for k, v in imp.items():
        vec[k] = v
    vec["DEPTH"] = dependency_depth(root, max_files)

    # normalize to unit vector
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


def composite_summary(root: Path) -> str:
    """Human-readable composite vector summary."""
    vec = composite_vector(root)
    # group by prefix
    groups = {}
    for k, v in vec.items():
        prefix = k.split(":")[0]
        groups.setdefault(prefix, []).append((k, v))
    lines = [f"Project: {root.name} — composite vector ({len(vec)} dims)"]
    for prefix in ["LANG", "PRIM", "FUNC", "CONN", "FLOW", "EFF", "SINK", "HARD", "IMP", "DEPTH"]:
        if prefix not in groups:
            continue
        items = sorted(groups[prefix], key=lambda kv: -kv[1])[:6]
        lines.append(f"  {prefix}: " + ", ".join(f"{k}={v:.3f}" for k, v in items))
    return "\n".join(lines)


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def project_similarity(root_a: Path, root_b: Path) -> float:
    """Compare two entire projects by their composite vectors."""
    return cosine(composite_vector(root_a), composite_vector(root_b))


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        # project A: python + js sum
        pa = base / "projA"
        pa.mkdir()
        (pa / "app.py").write_text("def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total")
        (pa / "ui.js").write_text("function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}")
        # project B: python sort + js filter
        pb = base / "projB"
        pb.mkdir()
        (pb / "app.py").write_text("def sort_asc(arr):\n    return sorted(arr)")
        (pb / "ui.js").write_text("function evens(nums) {\n    return nums.filter(n => n % 2 === 0);\n}")

        print("=== Full composite shape vector ===")
        print(composite_summary(pa))
        print()
        print(composite_summary(pb))
        print()
        print(f"projA vs projB similarity: {project_similarity(pa, pb):.3f}")
        print(f"projA vs projA similarity: {project_similarity(pa, pa):.3f}")
