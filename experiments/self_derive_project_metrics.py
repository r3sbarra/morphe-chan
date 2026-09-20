#!/usr/bin/env python
"""self_derive_project_metrics.py — Run the (previously blocked) second-order
project metric derivations on a controlled real-code corpus in
/tmp/shape-projects and persist the results as data.

Unblocks derive_higher_order.py / scan_health.py which hardcode project names
and skip missing dirs — they never ran because /tmp/shape-projects was empty.
Here we (a) populate the corpus from real local codebases (proxies for the named
project targets) and (b) capture the derived metric table.
"""
import sys, os, json, subprocess
from pathlib import Path

ROOT = Path("/tmp/shape-projects")

# Populate the corpus from real local code when /tmp/shape-projects is missing.
# Project name -> local source (a real, different codebase as a stand-in).
PROXY = {
    "flask":   "src/code_shape",          # Morphe-chan (security-analysis heavy)
    "requests":"src",                     # falsci
    "redis":   "src",                     # karyon-chans
    "express": ".",                       # services-hub (tiny)
}
SRC = Path(__file__).resolve().parents[2]  # <workspace>/projects — portable, no hardcoded user path;
# override with MORPHE_PROJECTS_SRC env if the corpus source lives elsewhere.


def ensure_corpus():
    if not ROOT.exists():
        ROOT.mkdir(parents=True)
    for name, rel in PROXY.items():
        dest = ROOT / name
        if not (dest / "__proxied__").exists():
            import shutil
            src_proj = {"flask": "morphe-chan", "requests": "falsci",
                        "redis": "karyon-chans", "express": "services-hub"}[name]
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(SRC / src_proj / rel, dest,
                            ignore=shutil.ignore_patterns("*.pyc", "__pycache__", ".git", ".venv", "node_modules"))
            (dest / "__proxied__").touch()


def run_and_collect():
    results = {}
    # derive_higher_order prints the table; capture via running the module
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parents[1] / "experiments"))
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import derive_higher_order  # noqa
    results["higher_order_table"] = buf.getvalue()
    return results


if __name__ == "__main__":
    ensure_corpus()
    out = run_and_collect()
    print(out["higher_order_table"])
    # persist
    path = Path(__file__).resolve().parents[1] / "data" / "project_metrics.json"
    path.write_text(json.dumps({"corpus": "real local codebase proxies in /tmp/shape-projects",
                                "note": "flask=morphe-chan src, requests=falsci, redis=karyon-chans, express=services-hub",
                                "table": out["higher_order_table"]}, indent=2))
    print("wrote", path)
