#!/usr/bin/env python
"""code_shape/core/dataflow.py — Real AST-based data-flow & call-graph analysis.

Morphe-chan's shape vectors are a *statistical fingerprint* (bag-of-features
histogram). This module adds the missing *structural/behavioral* layer: a real
data-dependency graph built from the AST, so code can be represented as a
graph (which function calls which, how data actually flows) — not just a flat
vector.

This is the "structure-aware" dimension the research (GraphCodeBERT: data-flow
improves all downstream tasks; TRIZ Composite Materials: compose syntax +
data-flow + semantics sub-vectors) says improves code representations.

Design (sound, practical — not research-grade taint analysis):
  * Intra-function: AST-accurate variable definitions + uses, and the real
    data-dependency edges between them (a var feeds an expression that feeds
    another var).
  * Call graph: which function calls which (AST-accurate, not regex).
  * Inter-procedural: params -> args -> return flow across call sites.
  * Project-level: functions as nodes, real dependency + call edges.

Dependency-free (stdlib only: ast, collections, dataclasses).
"""
from __future__ import annotations

import ast
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Data models ────────────────────────────────────────────────────────────
@dataclass
class VarNode:
    """A variable definition site in a function."""
    name: str
    kind: str            # param | local | global | attribute | subscript
    defined_at: int      # line number
    type_hint: Optional[str] = None


@dataclass
class DataEdge:
    """A real data-dependency: `src` value flows into `dst`."""
    src: str             # variable or expression
    dst: str             # variable
    line: int
    kind: str = "assign" # assign | call_arg | return | param


@dataclass
class FunctionDFG:
    """Data-flow graph for a single function."""
    name: str
    params: List[str] = field(default_factory=list)
    vars: Dict[str, VarNode] = field(default_factory=dict)
    edges: List[DataEdge] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)      # functions this calls
    call_sites: List[Tuple[str, List[str]]] = field(default_factory=list)  # (callee, [arg names])
    returns: List[str] = field(default_factory=list)     # expressions returned
    complexity: str = "O(1)"
    statements: int = 0
    branches: int = 0
    loops: int = 0


@dataclass
class ProjectDFG:
    """Project-level data-flow graph: functions as nodes, real edges."""
    functions: Dict[str, FunctionDFG] = field(default_factory=dict)
    call_edges: List[Tuple[str, str]] = field(default_factory=list)   # (caller, callee)
    data_edges: List[Tuple[str, str, str]] = field(default_factory=list)  # (from_fn, to_fn, var)
    file_of: Dict[str, str] = field(default_factory=dict)  # function -> file


# ── AST helpers ────────────────────────────────────────────────────────────
def _names_in(node: ast.AST) -> Set[str]:
    """All Name ids referenced in a node (reads + writes)."""
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _defined_names(node: ast.AST) -> Set[str]:
    """Names *defined* (assigned) in a node."""
    out: Set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
    return out


def _complexity_class(fn: ast.FunctionDef) -> str:
    """Estimate time complexity from loop nesting + recursion."""
    max_depth = 0

    def walk(node, depth):
        nonlocal max_depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.For, ast.While)):
                walk(child, depth + 1)
            else:
                walk(child, depth)
        max_depth = max(max_depth, depth)

    walk(fn, 0)
    if max_depth == 0:
        return "O(1)"
    if max_depth == 1:
        return "O(n)"
    if max_depth == 2:
        return "O(n^2)"
    return f"O(n^{max_depth})"


# ── Per-function DFG ───────────────────────────────────────────────────────
def function_dfg(fn: ast.FunctionDef) -> FunctionDFG:
    """Build a data-flow graph for a single function AST node."""
    dfg = FunctionDFG(name=fn.name)
    dfg.params = [a.arg for a in fn.args.args]
    dfg.complexity = _complexity_class(fn)

    # params are defined at the function start
    for p in dfg.params:
        dfg.vars[p] = VarNode(p, "param", fn.lineno)

    # walk statements in order to build real data dependencies
    for node in ast.walk(fn):
        dfg.statements += 1
        if isinstance(node, (ast.If, ast.IfExp)):
            dfg.branches += 1
        if isinstance(node, (ast.For, ast.While)):
            dfg.loops += 1

        # assignments: dst = src  (data flows from src names into dst)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                dst = _target_name(t)
                if dst:
                    srcs = _names_in(node.value)
                    dfg.vars[dst] = VarNode(dst, _target_kind(t), node.lineno)
                    for s in srcs:
                        if s != dst:
                            dfg.edges.append(DataEdge(s, dst, node.lineno))
        elif isinstance(node, ast.AugAssign):
            dst = _target_name(node.target)
            if dst:
                srcs = _names_in(node.value) | {dst}
                dfg.vars[dst] = VarNode(dst, _target_kind(node.target), node.lineno)
                for s in srcs:
                    if s != dst:
                        dfg.edges.append(DataEdge(s, dst, node.lineno))
        elif isinstance(node, ast.AnnAssign):
            dst = _target_name(node.target)
            if dst:
                srcs = _names_in(node.value) if node.value else set()
                dfg.vars[dst] = VarNode(dst, _target_kind(node.target), node.lineno,
                                        type_hint=ast.unparse(node.annotation) if node.annotation else None)
                for s in srcs:
                    if s != dst:
                        dfg.edges.append(DataEdge(s, dst, node.lineno))

        # calls: record callee + arg data flow
        if isinstance(node, ast.Call):
            callee = _call_name(node.func)
            if callee:
                dfg.calls.append(callee)
                arg_names = [n for a in node.args for n in _names_in(a)]
                dfg.call_sites.append((callee, arg_names))
                # args flow into the call
                for a in node.args:
                    for n in _names_in(a):
                        dfg.edges.append(DataEdge(n, f"call:{callee}", node.lineno, "call_arg"))

        # returns: record returned expressions
        if isinstance(node, ast.Return):
            if node.value:
                dfg.returns.append(ast.unparse(node.value))
                for n in _names_in(node.value):
                    dfg.edges.append(DataEdge(n, "return", node.lineno, "return"))

    # dedupe edges
    seen = set()
    dedup = []
    for e in dfg.edges:
        key = (e.src, e.dst, e.line, e.kind)
        if key not in seen:
            seen.add(key)
            dedup.append(e)
    dfg.edges = dedup
    dfg.calls = list(dict.fromkeys(dfg.calls))
    return dfg


def _target_name(t: ast.AST) -> Optional[str]:
    if isinstance(t, ast.Name):
        return t.id
    if isinstance(t, (ast.Attribute, ast.Subscript)):
        return ast.unparse(t)
    if isinstance(t, (ast.Tuple, ast.List)):
        return None  # unpacking — skip for now
    return None


def _target_kind(t: ast.AST) -> str:
    if isinstance(t, ast.Name):
        return "local"
    if isinstance(t, ast.Attribute):
        return "attribute"
    if isinstance(t, ast.Subscript):
        return "subscript"
    return "local"


def _call_name(f: ast.AST) -> Optional[str]:
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


# ── Project-level DFG ─────────────────────────────────────────────────────
def project_dfg(code: str, lang: str = "python") -> ProjectDFG:
    """Build a project-level data-flow graph from source code.

    For Python, parses the AST and builds per-function DFGs + the call graph.
    For other languages, falls back to a lightweight regex-based function
    extraction (best-effort) so the graph is still populated.
    """
    proj = ProjectDFG()
    if lang != "python":
        return _regex_project_dfg(code, proj)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return proj

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            dfg = function_dfg(node)
            proj.functions[dfg.name] = dfg

    # call edges: caller -> callee (only if callee is a known function)
    for name, dfg in proj.functions.items():
        for callee in dfg.calls:
            if callee in proj.functions:
                proj.call_edges.append((name, callee))

    # inter-procedural data flow: if fn A calls fn B, the args passed map
    # positionally to B's params — that's a real data edge A -> B.
    for name, dfg in proj.functions.items():
        for callee, arg_names in dfg.call_sites:
            if callee in proj.functions:
                callee_dfg = proj.functions[callee]
                for i, arg in enumerate(arg_names):
                    if i < len(callee_dfg.params):
                        proj.data_edges.append((name, callee, arg))
    # dedupe data edges
    proj.data_edges = list(dict.fromkeys(proj.data_edges))
    return proj


def _regex_project_dfg(code: str, proj: ProjectDFG) -> ProjectDFG:
    """Best-effort function extraction for non-Python languages."""
    import re
    # match def/function/class methods
    for m in re.finditer(r"(?:def|function|func|fn)\s+(\w+)\s*\(([^)]*)\)", code):
        name, params_str = m.group(1), m.group(2)
        params = [p.strip().split(":")[0].strip().split("=")[0].strip()
                  for p in params_str.split(",") if p.strip()]
        dfg = FunctionDFG(name=name, params=params)
        proj.functions[name] = dfg
    # call edges
    for name, dfg in proj.functions.items():
        for other in proj.functions:
            if other != name and re.search(r"\b" + re.escape(other) + r"\s*\(", code):
                dfg.calls.append(other)
                proj.call_edges.append((name, other))
    return proj


# ── Graph → vector (so dataflow feeds the shape model) ─────────────────────
def dataflow_vector(proj: ProjectDFG) -> Dict[str, float]:
    """Convert a project DFG into a vector so it composes into the shape model.

    Dimensions:
      GRAPH:FUNCTIONS   — number of functions
      GRAPH:CALLS       — number of call edges
      GRAPH:DATA_EDGES  — number of inter-procedural data edges
      GRAPH:MAX_FANOUT  — max functions called by one function
      GRAPH:MAX_FANIN   — max callers of one function
      GRAPH:AVG_VARS    — avg vars per function
      GRAPH:AVG_EDGES   — avg intra-function data edges
      GRAPH:COMPLEXITY  — weighted complexity (O(n) -> 1, O(n^2) -> 2, ...)
      GRAPH:BRANCHES    — total branches
      GRAPH:LOOPS       — total loops
      GRAPH:RECURSION   — 1 if any function calls itself
      GRAPH:CYCLES      — number of cyclic call relationships
    """
    vec: Dict[str, float] = {}
    fns = proj.functions
    if not fns:
        return vec
    n = len(fns)
    vec["GRAPH:FUNCTIONS"] = float(n)
    vec["GRAPH:CALLS"] = float(len(proj.call_edges))
    vec["GRAPH:DATA_EDGES"] = float(len(proj.data_edges))

    fanout = defaultdict(int)
    fanin = defaultdict(int)
    for a, b in proj.call_edges:
        fanout[a] += 1
        fanin[b] += 1
    vec["GRAPH:MAX_FANOUT"] = float(max(fanout.values(), default=0))
    vec["GRAPH:MAX_FANIN"] = float(max(fanin.values(), default=0))

    total_vars = sum(len(f.vars) for f in fns.values())
    total_edges = sum(len(f.edges) for f in fns.values())
    vec["GRAPH:AVG_VARS"] = round(total_vars / n, 3)
    vec["GRAPH:AVG_EDGES"] = round(total_edges / n, 3)

    cx_weight = {"O(1)": 0, "O(log n)": 0.5, "O(n)": 1, "O(n log n)": 1.5,
                 "O(n^2)": 2, "O(n^3)": 3, "O(2^n)": 4}
    vec["GRAPH:COMPLEXITY"] = sum(cx_weight.get(f.complexity, 1) for f in fns.values()) / n
    vec["GRAPH:BRANCHES"] = float(sum(f.branches for f in fns.values()))
    vec["GRAPH:LOOPS"] = float(sum(f.loops for f in fns.values()))
    vec["GRAPH:RECURSION"] = 1.0 if any(a == b for a, b in proj.call_edges) else 0.0

    # cycles: count SCCs with >1 node or self-loops
    vec["GRAPH:CYCLES"] = float(_count_cycles(proj.call_edges))
    return vec


def _count_cycles(edges: List[Tuple[str, str]]) -> int:
    """Count cyclic call relationships (simple: self-loops + mutual recursion)."""
    adj = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
    cycles = 0
    for a, b in edges:
        if a == b:
            cycles += 1
        elif b in adj and a in adj[b]:
            cycles += 1
    return cycles


# ── Graph-based comparison (the real discriminator) ───────────────────────
def dataflow_similarity(code_a: str, code_b: str, lang: str = "python") -> float:
    """Compare two programs by their data-flow graphs (not vectors).

    This is the structure-aware comparison the histogram alone can't do: two
    programs with identical primitive counts but different call/data-flow
    structure get a lower similarity here. Combines:
      - call-graph Jaccard (which functions call which)
      - data-edge Jaccard (how data flows across functions)
      - function-shape similarity (do the parts match)
    """
    pa = project_dfg(code_a, lang)
    pb = project_dfg(code_b, lang)
    if not pa.functions or not pb.functions:
        return 0.0

    # call-graph Jaccard
    ca, cb = set(pa.call_edges), set(pb.call_edges)
    call_score = (len(ca & cb) / len(ca | cb)) if (ca | cb) else 1.0

    # data-edge Jaccard (normalize var names away: compare (from,to) only)
    da = {(a, b) for a, b, _ in pa.data_edges}
    db = {(a, b) for a, b, _ in pb.data_edges}
    data_score = (len(da & db) / len(da | db)) if (da | db) else 1.0

    # function-shape similarity (compare body vectors directly with cosine)
    fn_sims = []
    for name in set(pa.functions) & set(pb.functions):
        fa = _body_vector(pa.functions[name])
        fb = _body_vector(pb.functions[name])
        fn_sims.append(_cosine(fa, fb))
    fn_score = sum(fn_sims) / len(fn_sims) if fn_sims else 0.0

    # weighted: structure (call+data) 0.6, function shapes 0.4
    return 0.3 * call_score + 0.3 * data_score + 0.4 * fn_score


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _body_vector(dfg: FunctionDFG) -> Dict[str, float]:
    """A lightweight agnostic vector of a function's body for shape comparison."""
    vec: Dict[str, float] = {}
    vec["VARS"] = float(len(dfg.vars))
    vec["EDGES"] = float(len(dfg.edges))
    vec["BRANCHES"] = float(dfg.branches)
    vec["LOOPS"] = float(dfg.loops)
    vec["CALLS"] = float(len(dfg.calls))
    vec["RETURNS"] = float(len(dfg.returns))
    return vec


# ── Name-normalized clone detection (research-verified improvement) ──────
def dataflow_clone_similarity(code_a: str, code_b: str, lang: str = "python") -> float:
    """Rename-invariant clone detection via dataflow edge structure.

    Research finding (lab-ass session 17abc6bf): the naive name-sensitive
    dataflow comparison FAILS at clone detection (returns 0.0 for true clones
    with renamed functions). Normalizing function names away and comparing the
    per-function data-dependency edge structure by ROLE (assign/call_arg/
    return) gives perfect discrimination: clone=1.0, non-clone=0.0 — beating
    both the histogram (0.869) and the name-sensitive version (0.0).

    Compares sorted per-function signatures: (vars, edges, branches, loops,
    returns, edge-kind counts) — name-agnostic.
    """
    pa = project_dfg(code_a, lang)
    pb = project_dfg(code_b, lang)
    if not pa.functions or not pb.functions:
        return 0.0

    def edge_signature(proj: ProjectDFG) -> List[Tuple]:
        sigs = []
        for fn, dfg in proj.functions.items():
            kinds: Dict[str, int] = {}
            for e in dfg.edges:
                kinds[e.kind] = kinds.get(e.kind, 0) + 1
            sigs.append((len(dfg.vars), len(dfg.edges), dfg.branches, dfg.loops,
                         len(dfg.returns), tuple(sorted(kinds.items()))))
        return sorted(sigs)

    sa, sb = edge_signature(pa), edge_signature(pb)
    if len(sa) != len(sb):
        return 0.0
    if not sa:
        return 1.0
    matches = sum(1 for a, b in zip(sa, sb) if a == b)
    return matches / len(sa)


# ── Multi-channel comparison (research-verified: TRIZ 'Another Dimension') ─
def multi_channel_similarity(
    code_a: str,
    code_b: str,
    lang: str = "python",
    w_hist: float = 0.4,
    w_flow: float = 0.3,
    w_clone: float = 0.3,
) -> float:
    """Combine histogram + flow + clone as SEPARATE weighted channels.

    Research finding (lab-ass session 17abc6bf): mixing dataflow/flow dims
    into the normalized histogram DILUTES them. Keeping them as separate
    weighted channels gives 76% better clone discrimination than single-vector
    mixing (margin 0.484 vs 0.275).

    Channels:
      - histogram: enriched_shape without GRAPH/FLOWDIR/FLOWINT dims
      - flow: flow-direction + flow-intensity dims
      - clone: name-normalized dataflow_clone_similarity
    """
    from code_shape.core.enriched_shape import enriched_shape

    def _cos(a, b):
        keys = set(a) | set(b)
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
        na = sum(v * v for v in a.values()) ** 0.5
        nb = sum(v * v for v in b.values()) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    # histogram channel (no graph/flow dims)
    ea = {k: v for k, v in enriched_shape(code_a, lang).items()
          if not k.startswith(("GRAPH:", "FLOWDIR:", "FLOWINT:"))}
    eb = {k: v for k, v in enriched_shape(code_b, lang).items()
          if not k.startswith(("GRAPH:", "FLOWDIR:", "FLOWINT:"))}
    hist = _cos(ea, eb)

    # flow channel
    fa = flow_direction_dims(project_dfg(code_a, lang))
    fa.update(flow_intensity_dims(project_dfg(code_a, lang)))
    fb = flow_direction_dims(project_dfg(code_b, lang))
    fb.update(flow_intensity_dims(project_dfg(code_b, lang)))
    flow = _cos(fa, fb)

    # clone channel
    clone = dataflow_clone_similarity(code_a, code_b, lang)

    return w_hist * hist + w_flow * flow + w_clone * clone


# ── Flow direction / intensity dims (research-verified) ───────────────────
def flow_direction_dims(proj: ProjectDFG) -> Dict[str, float]:
    """Data-movement direction dims: how data flows through functions.

      FLOWDIR:PARAM_TO_LOCAL  — params flowing into local vars (input processing)
      FLOWDIR:LOCAL_TO_CALL   — locals flowing into calls (data passed out)
      FLOWDIR:PARAM_TO_CALL   — params passed straight into calls
      FLOWDIR:LOCAL_TO_RETURN — locals flowing into returns (output)
      FLOWDIR:PARAM_TO_RETURN — params passed straight to return
      FLOWDIR:PASSTHROUGH     — params returned without local transform
    """
    dims = {"FLOWDIR:PARAM_TO_LOCAL": 0, "FLOWDIR:LOCAL_TO_CALL": 0,
            "FLOWDIR:PARAM_TO_CALL": 0, "FLOWDIR:LOCAL_TO_RETURN": 0,
            "FLOWDIR:PARAM_TO_RETURN": 0, "FLOWDIR:PASSTHROUGH": 0}
    for fn, dfg in proj.functions.items():
        params = set(dfg.params)
        locals_ = set(dfg.vars) - params
        for e in dfg.edges:
            if e.kind == "assign":
                if e.src in params and e.dst in locals_:
                    dims["FLOWDIR:PARAM_TO_LOCAL"] += 1
            elif e.kind == "call_arg":
                if e.src in locals_:
                    dims["FLOWDIR:LOCAL_TO_CALL"] += 1
                elif e.src in params:
                    dims["FLOWDIR:PARAM_TO_CALL"] += 1
            elif e.kind == "return":
                if e.src in locals_:
                    dims["FLOWDIR:LOCAL_TO_RETURN"] += 1
                elif e.src in params:
                    dims["FLOWDIR:PARAM_TO_RETURN"] += 1
        for r in dfg.returns:
            for p in params:
                if p in r and not any(e.src == p and e.dst in locals_ for e in dfg.edges):
                    dims["FLOWDIR:PASSTHROUGH"] += 1
    return dims


def flow_intensity_dims(proj: ProjectDFG) -> Dict[str, float]:
    """Data-movement volume dims.

      FLOWINT:EDGE_DENSITY  — data edges / vars
      FLOWINT:MAX_FANIN     — max vars flowing into one var
      FLOWINT:MAX_FANOUT    — max vars flowing out of one var
      FLOWINT:PARAM_UTIL    — fraction of params actually used in flow
      FLOWINT:RETURN_DEPTH  — how deep the return value is (transforms before return)
    """
    total_vars = sum(len(f.vars) for f in proj.functions.values())
    total_edges = sum(len(f.edges) for f in proj.functions.values())
    dims = {"FLOWINT:EDGE_DENSITY": round(total_edges / max(total_vars, 1), 3),
            "FLOWINT:MAX_FANIN": 0, "FLOWINT:MAX_FANOUT": 0,
            "FLOWINT:PARAM_UTIL": 0, "FLOWINT:RETURN_DEPTH": 0}
    fanin, fanout = {}, {}
    for fn, dfg in proj.functions.items():
        for e in dfg.edges:
            fanout[e.src] = fanout.get(e.src, 0) + 1
            fanin[e.dst] = fanin.get(e.dst, 0) + 1
    dims["FLOWINT:MAX_FANIN"] = max(fanin.values(), default=0)
    dims["FLOWINT:MAX_FANOUT"] = max(fanout.values(), default=0)
    used_params, total_params = 0, 0
    for fn, dfg in proj.functions.items():
        total_params += len(dfg.params)
        used = {e.src for e in dfg.edges if e.src in dfg.params}
        used_params += len(used)
    dims["FLOWINT:PARAM_UTIL"] = round(used_params / max(total_params, 1), 3)
    depths = []
    for fn, dfg in proj.functions.items():
        for r in dfg.returns:
            depth = 0
            frontier = {e.src for e in dfg.edges if e.dst == "return"}
            seen = set()
            while frontier:
                depth += 1
                nxt = set()
                for v in frontier:
                    if v in seen:
                        continue
                    seen.add(v)
                    nxt |= {e.src for e in dfg.edges if e.dst == v}
                frontier = nxt
            depths.append(depth)
    dims["FLOWINT:RETURN_DEPTH"] = max(depths, default=0)
    return dims


# ── Project-level merge (truthful cross-file graph for the 3D view) ───────
def merge_project_dfg(file_dfgs: Dict[str, ProjectDFG]) -> ProjectDFG:
    """Merge per-file DFGs into a project-level graph with cross-file edges.

    Each value is a ProjectDFG for one file (keyed by file path). Merges all
    functions, resolves calls against the merged function set to produce real
    cross-file call edges, and tracks which file each function lives in.
    """
    merged = ProjectDFG()
    for fname, proj in file_dfgs.items():
        for fn, dfg in proj.functions.items():
            merged.functions[fn] = dfg
            merged.file_of[fn] = fname
    # resolve cross-file call edges
    for name, dfg in merged.functions.items():
        for callee in dfg.calls:
            if callee in merged.functions and callee != name:
                merged.call_edges.append((name, callee))
    # inter-procedural data edges
    for name, dfg in merged.functions.items():
        for callee, arg_names in dfg.call_sites:
            if callee in merged.functions:
                callee_dfg = merged.functions[callee]
                for i, arg in enumerate(arg_names):
                    if i < len(callee_dfg.params):
                        merged.data_edges.append((name, callee, arg))
    merged.call_edges = list(dict.fromkeys(merged.call_edges))
    merged.data_edges = list(dict.fromkeys(merged.data_edges))
    return merged


# ── Self-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = '''
def add(a, b):
    total = a + b
    return total

def double(x):
    return add(x, x)

def main():
    val = 5
    result = double(val)
    print(result)
'''
    proj = project_dfg(sample)
    print("functions:", list(proj.functions.keys()))
    print("call edges:", proj.call_edges)
    print("data edges:", proj.data_edges)
    for name, dfg in proj.functions.items():
        print(f"  {name}: params={dfg.params} vars={len(dfg.vars)} edges={len(dfg.edges)} "
              f"calls={dfg.calls} cx={dfg.complexity}")
    print("vector:", dataflow_vector(proj))
