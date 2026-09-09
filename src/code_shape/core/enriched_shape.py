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
from code_shape.security.vuln_v2 import detect_vulns_v2


def _data_properties(code: str) -> Dict[str, float]:
    """Data properties: types, sizes, mutability."""
    props = {}
    if re.search(r"str\s*\(|\.upper\s*\(|\.lower\s*\(|\.strip\s*\(|\.split\s*\(", code):
        props["PROP:STR"] = 1
    if re.search(r"int\s*\(|float\s*\(|\b\d+\.\d+\b", code):
        props["PROP:NUM"] = 1
    if re.search(r"\[\s*\]|list\s*\(|\.append\s*\(|\.extend\s*\(", code):
        props["PROP:LIST"] = 1
    if re.search(r"\{\s*\}|dict\s*\(|\.get\s*\(|\.keys\s*\(", code):
        props["PROP:DICT"] = 1
    if re.search(r"\.append\s*\(|\.add\s*\(|\.insert\s*\(|\.remove\s*\(", code):
        props["PROP:MUTABLE"] = 1
    if re.search(r"\.upper\s*\(|\.lower\s*\(|\.strip\s*\(|\.replace\s*\(", code):
        props["PROP:TRANSFORM"] = 1
    return props


def _control_properties(code: str) -> Dict[str, float]:
    """Control properties: branching, loops, recursion."""
    props = {}
    branches = len(re.findall(r"\bif\b|\belse\b|\belif\b|\bswitch\b|\bcase\b", code))
    if branches:
        props["PROP:BRANCHES"] = branches
    loops = len(re.findall(r"\bfor\b|\bwhile\b", code))
    if loops:
        props["PROP:LOOPS"] = loops
    if re.search(r"recurs|factorial\(|fibonacci\(|def\s+\w+.*\b\w+\s*\(", code):
        props["PROP:RECURSIVE"] = 1
    if re.search(r"try\s*:|except\s+|catch\s*\(", code):
        props["PROP:HANDLES_ERRORS"] = 1
    return props


def _io_properties(code: str) -> Dict[str, float]:
    """I/O properties: inputs, outputs, side effects."""
    props = {}
    params = len(re.findall(r"def\s+\w+\s*\(([^)]*)\)", code))
    if params:
        props["PROP:INPUTS"] = params
    returns = len(re.findall(r"\breturn\b", code))
    if returns:
        props["PROP:OUTPUTS"] = returns
    if re.search(r"\bprint\s*\(|console\.log|\.write\s*\(|\.send\s*\(", code):
        props["PROP:SIDE_EFFECTS"] = 1
    if re.search(r"\bopen\s*\(|requests\.|\.get\s*\(|\.post\s*\(", code):
        props["PROP:IO"] = 1
    return props


def _derived_values(code: str, lang: str) -> Dict[str, float]:
    """NEW derived values: flow depth, branching, coupling, risk."""
    vals = {}
    # data flow depth (assignments between input and output)
    assigns = len(re.findall(r"\w+\s*=\s*[^;\n]+", code))
    vals["VAL:FLOW_DEPTH"] = assigns
    # branching factor
    branches = len(re.findall(r"\bif\b|\belse\b|\belif\b", code))
    vals["VAL:BRANCHING"] = branches
    # coupling (libraries + patterns + algorithms)
    libs = len(detect_library_sinks(code, lang))
    pats = len(detect_patterns(code, lang))
    algs = len(detect_algorithm(code, lang))
    vals["VAL:COUPLING"] = libs + pats + algs
    # risk score (vulns + weak crypto)
    vulns = len(detect_vulns_v2(code, lang))
    vals["VAL:RISK"] = vulns
    return vals


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
    # vulns
    for v in detect_vulns_v2(code, lang):
        vec[f"VULN:{v['type']}"] = vec.get(f"VULN:{v['type']}", 0) + 1
    # properties
    for k, v in _data_properties(code).items():
        vec[k] = v
    for k, v in _control_properties(code).items():
        vec[k] = v
    for k, v in _io_properties(code).items():
        vec[k] = v
    # derived values
    for k, v in _derived_values(code, lang).items():
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
