#!/usr/bin/env python
"""enriched_shape.py — Truly multi-dimensional shape with properties + values.
classes/programs have a truly multi-dimensional representation:

  PRIM:<primitive>   — intent/structure primitives (23)
  EFF:<dim>          — efficiency (8)
  FLOW:<op>          — value-flow transforms
  LIB:<role>         — library roles used
  ALG:<algorithm>    — algorithms detected
  PAT:<pattern>      — design/data/concurrency patterns
  VULN:<type>        — vulnerabilities
  PROP:<property>    — data/control/I-O properties (NEW)
  VAL:<value>        — new values derived (NEW)

The PROP dimensions capture:
  - data types (str/int/list/dict)
  - control (branching, loops, recursion)
  - I/O (input count, output count, side effects)
  - complexity signals

The VAL dimensions capture NEW derived values:
  - data flow depth (how deep values flow)
  - branching factor
  - coupling (how many libraries/patterns)
  - risk score (vulns + weak crypto)

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List

from code_shape.core.code_shape_core import true_shape_vector, PRIMITIVES
from code_shape.analysis.efficiency_shape import efficiency_vector, EFF_DIMS
from code_shape.core.value_flow_shape import value_flow_shape
from code_shape.core.variable_shape import (
    infer_types, variable_shape, variable_shape_normalized,
    cascading_type_flow, merge_variable_shape,
)
from code_shape.security.library_shapes import detect_library_sinks
from code_shape.analysis.algorithm_detector import detect_algorithm
from code_shape.analysis.pattern_detector import detect_patterns


def _data_properties(code: str) -> Dict[str, float]:
    """Data properties: types, sizes, mutability (lexer-aware)."""
    from code_shape.core.agnostic_shape import _tokenize, _strip_strings_and_comments
    stripped = _strip_strings_and_comments(code)
    toks = _tokenize(code)
    props = {}
    if any(t in ("str", "float", "int") for t in toks) or re.search(r"\b\d+\.\d+\b", stripped):
        props["PROP:NUM"] = 1
    if any(t in ("list", "tuple", "set", "dict") for t in toks) or any(
        toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("append", "extend", "keys", "values", "items", "get")
        for i in range(len(toks) - 1)
    ):
        props["PROP:LIST"] = 1
    if any(t == "{" for t in toks) or any(
        toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("get", "keys", "values", "items")
        for i in range(len(toks) - 1)
    ):
        props["PROP:DICT"] = 1
    if any(
        toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("append", "add", "insert", "remove", "pop", "extend", "update", "set")
        for i in range(len(toks) - 1)
    ):
        props["PROP:MUTABLE"] = 1
    if any(
        toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("upper", "lower", "strip", "replace", "split", "join")
        for i in range(len(toks) - 1)
    ):
        props["PROP:TRANSFORM"] = 1
    return props


def _control_properties(code: str) -> Dict[str, float]:
    """Control properties: branching, loops, recursion (lexer-aware)."""
    from code_shape.core.agnostic_shape import _tokenize
    toks = _tokenize(code)
    props = {}
    branches = sum(1 for t in toks if t in ("if", "else", "elif", "switch", "case", "when"))
    if branches:
        props["PROP:BRANCHES"] = branches
    loops = sum(1 for t in toks if t in ("for", "while", "foreach", "until", "repeat"))
    if loops:
        props["PROP:LOOPS"] = loops
    if any(t in ("try", "except", "finally", "catch", "throw") for t in toks):
        props["PROP:HANDLES_ERRORS"] = 1
    return props


def _io_properties(code: str) -> Dict[str, float]:
    """I/O properties: inputs, outputs, side effects (lexer-aware)."""
    from code_shape.core.agnostic_shape import _tokenize, _strip_strings_and_comments
    stripped = _strip_strings_and_comments(code)
    toks = _tokenize(code)
    props = {}
    m = re.search(r"(?:def|function|func|fun)\s+\w+\s*\(([^)]*)\)", stripped)
    if m:
        params = [p for p in m.group(1).split(",") if p.strip()]
        props["PROP:INPUTS"] = len(params)
    returns = sum(1 for t in toks if t == "return")
    if returns:
        props["PROP:OUTPUTS"] = returns
    if any(t in ("print", "printf", "puts", "echo") for t in toks) or any(
        toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("write", "send", "emit", "log")
        for i in range(len(toks) - 1)
    ):
        props["PROP:SIDE_EFFECTS"] = 1
    if re.search(r"\b(?:open|read|write|requests|urlopen|fetch)\s*\(", stripped):
        props["PROP:IO"] = 1
    return props


def _derived_values(code: str, lang: str, issues=None) -> Dict[str, float]:
    """NEW derived values: flow depth, branching, coupling, risk.

    FLOW_DEPTH / BRANCHING are lexer-aware (no phantom counts from strings,
    comments, or `=` inside `!=`). RISK is now a real severity-weighted risk
    score (0..1) from the precise-issues pipeline instead of a raw vuln count
    (detect_vulns_v2 returned empty on many common cases, so VAL:RISK was
    near-useless). Adds VAL:SEVERITY (worst-case label)."""
    from code_shape.core.agnostic_shape import _tokenize, _strip_strings_and_comments
    toks = _tokenize(code)
    vals = {}
    # data flow depth: real assignment tokens (not `=` inside !=/<=/==), strings stripped
    assigns = sum(1 for t in toks if t in ("=", "+=", "-=", "*=", "/=", "%="))
    vals["VAL:FLOW_DEPTH"] = assigns
    # branching factor: distinct branch decisions
    branches = sum(1 for t in toks if t in ("if", "elif", "when", "switch", "case"))
    vals["VAL:BRANCHING"] = branches
    # coupling: distinct external dependencies (library roles + import/require/use)
    try:
        libs = len({s.get("role") for s in detect_library_sinks(code, lang)})
    except Exception:
        libs = 0
    imports = sum(1 for t in toks if t in ("import", "from", "require", "include", "use"))
    vals["VAL:COUPLING"] = libs + imports
    # risk: severity-weighted score + worst severity rank from precise issues
    risk, sev = _risk_from_issues(issues if issues is not None else _find_precise_issues(code))
    vals["VAL:RISK"] = risk
    if sev:
        # numeric severity rank (1..4) so the vector stays numeric-normalizable
        vals["VAL:SEVERITY"] = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(sev, 1)
    return vals


def _risk_score(code: str):
    """Return (risk_score 0..1, worst_severity_label) from precise-issues,
    weighting by per-finding severity/exploitability instead of a raw count."""
    return _risk_from_issues(_find_precise_issues(code))


def _find_precise_issues(code: str):
    """Run the precise-issues detector once so the VULN dims and the risk
    score share the same (authoritative) findings instead of running two
    separate vuln pipelines per enriched_shape call."""
    try:
        from code_shape.security.precise_issues import find_precise_issues
        return find_precise_issues(code)
    except Exception:
        return []


def _risk_from_issues(issues):
    """Risk score + worst severity from a list of precise-issue findings."""
    sev_weight = {"LOW": 0.2, "MEDIUM": 0.4, "HIGH": 0.7, "CRITICAL": 1.0}
    if not issues:
        return 0.0, None
    worst = 0.0
    worst_sev = None
    for it in issues:
        sev = (it.get("severity") or "").upper()
        w = sev_weight.get(sev, 0.0)
        expl = it.get("exploitability") or {}
        s = expl.get("score") if isinstance(expl, dict) else None
        if isinstance(s, (int, float)):
            w = max(w, min(1.0, s))
        if w > worst:
            worst = w
            worst_sev = sev or (expl.get("label") if isinstance(expl, dict) else None)
    return round(worst, 3), worst_sev


def enriched_shape(code: str, lang: str = "python") -> Dict[str, float]:
    """Truly multi-dimensional shape: primitives + efficiency + flow + library
    + algorithm + pattern + vuln + properties + derived values."""
    vec: Dict[str, float] = {}
    # primitives
    for k, v in true_shape_vector(code, lang).items():
        vec[f"PRIM:{k}"] = v
    # efficiency
    for k, v in efficiency_vector(code).items():
        vec[f"EFF:{k}"] = v
    # value flow
    for k, v in value_flow_shape(code).items():
        vec[k] = v
    # library roles
    for s in detect_library_sinks(code, lang):
        vec[f"LIB:{s['role']}"] = vec.get(f"LIB:{s['role']}", 0) + 1
    # algorithms
    for a in detect_algorithm(code, lang):
        vec[f"ALG:{a['algorithm']}"] = vec.get(f"ALG:{a['algorithm']}", 0) + 1
    # patterns
    for p in detect_patterns(code, lang):
        vec[f"PAT:{p['pattern']}"] = vec.get(f"PAT:{p['pattern']}", 0) + 1
    # vulns: use precise-issues findings (also feeds VAL:RISK) — single run
    precise = _find_precise_issues(code)
    for v in precise:
        vec[f"VULN:{v['type']}"] = vec.get(f"VULN:{v['type']}", 0) + 1
    # properties
    for k, v in _data_properties(code).items():
        vec[k] = v
    for k, v in _control_properties(code).items():
        vec[k] = v
    for k, v in _io_properties(code).items():
        vec[k] = v
    # derived values (share the precise-issues findings with the vuln loop)
    for k, v in _derived_values(code, lang, issues=precise).items():
        vec[k] = v
    # param & variable shapes (data dimension)
    for k, v in variable_shape(code, lang).items():
        vec[k] = v
    # data-flow / call-graph structure (GRAPH:* dims) — the structure-aware
    # layer the research says improves code representations (GraphCodeBERT).
    try:
        from code_shape.core.dataflow import project_dfg, dataflow_vector
        _proj = project_dfg(code, lang=lang)
        for k, v in dataflow_vector(_proj).items():
            vec[k] = v
    except Exception:
        pass
    # NEW self-derived shape metrics (rename-invariant richnes/concentration):
    # SHAPE_ENTROPY / SHAPE_SPREAD / SHAPE_SKEW over the name-invariant dims.
    # Computed on the RAW vec before normalization so signal magnitude is real.
    from code_shape.core.shape_metrics import shape_metrics
    vec.update(shape_metrics(vec))
    # NEW: wire the STATE/DATA/CTRL/IFACE/RES dims (new_shape_dims) into the
    # enriched vector. These (cyclomatic complexity, statefulness, resource use,
    # interface arity) were defined but never integrated into enriched_shape.
    from code_shape.core import new_shape_dims as _nsd
    for _fn in (_nsd.state_dims, _nsd.data_dims, _nsd.control_dims,
                _nsd.interface_dims, _nsd.resource_dims):
        try:
            for _k, _v in _fn(code).items():
                vec[_k] = _v
        except Exception:
            pass
    # normalize
    norm = math.sqrt(sum(x * x for x in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


def enriched_summary(code: str, lang: str = "python") -> str:
    """Human-readable enriched shape summary."""
    vec = enriched_shape(code, lang)
    groups = {}
    for k, v in vec.items():
        prefix = k.split(":")[0]
        groups.setdefault(prefix, []).append((k, v))
    lines = []
    for prefix in ["PRIM", "EFF", "FLOW", "LIB", "ALG", "PAT", "VULN", "PROP", "VAL"]:
        if prefix not in groups:
            continue
        items = sorted(groups[prefix], key=lambda kv: -kv[1])[:4]
        lines.append(f"  {prefix}: " + ", ".join(f"{k}={v:.2f}" for k, v in items))
    return "\n".join(lines)


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    code = "def process(data):\n    result = data.strip()\n    return result.upper()"
    print("=== Enriched multi-dimensional shape ===")
    print(enriched_summary(code))
    print(f"total dims: {len(enriched_shape(code))}")
