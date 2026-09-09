#!/usr/bin/env python
"""library_shapes.py — Library/module shapes for language adapters.
language from the data directory:

  data/libraries/<language>/v1/libraries.json

Each library call is classified by its semantic role (web-input, SQL, file,
exec, render, deserialize, crypto, etc.), so the adapter can recognize and
shape library usage.

This enables:
  1. SINK detection — `requests.get(url)` is SSRF, `db.execute(sql)` is SQLi
  2. INPUT detection — `flask.request`, `express.req` is untrusted input
  3. Better decomposition — library-heavy code is shaped correctly

Dependency-free (stdlib only).
"""
import json
import re
from pathlib import Path
from typing import Dict, List

# ── Load library shapes from data directory ────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "libraries"


def _load_library_shapes() -> Dict[str, Dict]:
    """Load all library shapes from data/libraries/<lang>/v1/libraries.json.

    Returns {lang: {'third_party': {...}, 'stdlib': {...}}}.
    """
    shapes = {}
    if not _DATA_DIR.is_dir():
        return shapes
    for lang_dir in sorted(_DATA_DIR.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name.startswith("_"):
            continue
        versions = sorted([d for d in lang_dir.iterdir() if d.is_dir()])
        if not versions:
            continue
        latest = versions[-1]
        lib_file = latest / "libraries.json"
        if lib_file.exists():
            try:
                data = json.loads(lib_file.read_text())
                shapes[lang_dir.name] = {
                    "third_party": data.get("libraries", {}),
                    "stdlib": data.get("stdlib", {}),
                }
            except Exception:
                continue
    return shapes


def _load_role_danger() -> Dict[str, float]:
    """Load the role->danger map from data/libraries/_meta/roles.json."""
    meta_file = _DATA_DIR / "_meta" / "roles.json"
    if meta_file.exists():
        try:
            data = json.loads(meta_file.read_text())
            return data.get("role_danger", {})
        except Exception:
            pass
    return {}


LIBRARY_SHAPES = _load_library_shapes()
ROLE_DANGER = _load_role_danger()


def library_role(lang: str, module: str, call: str) -> str:
    """Get the semantic role of a library call. Returns role or None.

    Checks both stdlib (default modules) and third-party libraries.
    """
    lang_data = LIBRARY_SHAPES.get(lang, {})
    for source in ("stdlib", "third_party"):
        libs = lang_data.get(source, {})
        # exact module match
        if module in libs:
            call_map = libs[module]
            if call in call_map:
                return call_map[call]
            if "" in call_map:
                return call_map[""]
        # module prefix match (e.g. os.path.join -> os) with word boundary
        for mod, call_map in libs.items():
            if module == mod or module.startswith(mod + "."):
                if call in call_map:
                    return call_map[call]
                if "" in call_map:
                    return call_map[""]
    return None


def library_source(lang: str, module: str) -> str:
    """Return 'stdlib' or 'third_party' for a module, or None."""
    lang_data = LIBRARY_SHAPES.get(lang, {})
    for source in ("stdlib", "third_party"):
        libs = lang_data.get(source, {})
        for mod in libs:
            if module == mod or module.startswith(mod + "."):
                return source
    return None


def detect_library_sinks(code: str, lang: str) -> List[Dict]:
    """Detect dangerous library calls by their library shape.

    Resolves aliases: `db = sqlite3.connect(...)` then `db.execute(...)` is
    recognized as sqlite3.execute.
    """
    findings = []
    # resolve aliases: var = module.func(...) or var = module or var = Class(...)
    aliases = {}
    for m in re.finditer(r"(\w+)\s*=\s*([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\s*\(", code):
        aliases[m.group(1)] = m.group(2).split(".")[0]
    for m in re.finditer(r"(\w+)\s*=\s*([a-zA-Z_]\w*)\s*$", code, re.MULTILINE):
        aliases[m.group(1)] = m.group(2)
    # var = Class(...) alias (e.g. soup = BeautifulSoup(...))
    for m in re.finditer(r"(\w+)\s*=\s*([A-Z]\w*)\s*\(", code):
        aliases[m.group(1)] = m.group(2)
    # JS require alias: const cp = require('child_process')
    for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]", code):
        aliases[m.group(1)] = m.group(2)
    # Java: Runtime.getRuntime().exec -> java.lang Runtime exec
    for m in re.finditer(r"Runtime\.getRuntime\(\)\.(\w+)\s*\(", code):
        findings.append({"module": "java.lang", "call": m.group(1), "role": "EXEC",
                        "danger": 1.0, "full": f"Runtime.getRuntime().{m.group(1)}"})

    # find module-qualified calls: module.func(...) or module.sub.func(...)
    for m in re.finditer(r"([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\s*\(", code):
        full = m.group(1)
        parts = full.split(".")
        if len(parts) < 2:
            continue
        call = parts[-1]
        module = ".".join(parts[:-1])
        # resolve alias in module
        if module in aliases:
            module = aliases[module]
        role = library_role(lang, module, call)
        if role and ROLE_DANGER.get(role, 0) >= 0.6:
            findings.append({
                "module": module,
                "call": call,
                "role": role,
                "danger": ROLE_DANGER[role],
                "full": full,
                "source": library_source(lang, module),
            })
    return findings


def library_shape(code: str, lang: str) -> Dict[str, float]:
    """Library-shape of a code snippet: which library roles are present."""
    import math
    sinks = detect_library_sinks(code, lang)
    vec: Dict[str, float] = {}
    for s in sinks:
        vec[f"LIB:{s['role']}"] = vec.get(f"LIB:{s['role']}", 0) + s["danger"]
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Loaded {len(LIBRARY_SHAPES)} languages from data/libraries/")
    cases = {
        "python": "import requests\nimport sqlite3\ndef f(request):\n    url = request.args['url']\n    r = requests.get(url)\n    db = sqlite3.connect('x.db')\n    db.execute('SELECT * FROM users WHERE name = ' + request.form['name'])\n    return r.text",
        "javascript": "const fs = require('fs');\nconst cp = require('child_process');\nfunction f(req) {\n    cp.exec('ls ' + req.query.cmd);\n    fs.readFile('/etc/passwd');\n}",
        "java": "import java.sql.*;\nimport java.lang.*;\npublic void f(HttpServletRequest req) {\n    Statement s = conn.createStatement();\n    s.executeQuery('SELECT * FROM users WHERE name = ' + req.getParameter('name'));\n    Runtime.getRuntime().exec('ls');\n}",
    }
    print("=== Library-shape sink detection (loaded from data) ===")
    for lang, code in cases.items():
        sinks = detect_library_sinks(code, lang)
        print(f"{lang}: {[(s['module'], s['call'], s['role'], s.get('source')) for s in sinks]}")
