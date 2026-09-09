"""Research: which dataflow-derived dimensions add signal beyond the histogram?

Tests candidate graph-theoretic / dataflow dimensions against a discrimination
task: can they distinguish structurally-different code that the histogram
treats as near-identical? Also tests whether they improve clone detection.

Candidate dimensions (computed from the dataflow graph):
  * GRAPH:MAX_CALL_DEPTH   — longest call chain (a->b->c)
  * GRAPH:AVG_CALL_DEPTH   — mean call depth
  * GRAPH:COUPLING         — call edges / functions (density)
  * GRAPH:COHESION         — intra-file calls / total calls
  * GRAPH:CENTRALITY       — max degree centrality (hub function)
  * GRAPH:CLUSTERING       — avg clustering coefficient
  * GRAPH:DATAFLOW_DEPTH   — longest data-dependency chain within functions
  * GRAPH:PARAM_FANIN      — avg params per function (input surface)
  * GRAPH:RETURN_FANOUT    — avg returns per function (output surface)
  * GRAPH:RECURSION_DEPTH  — recursion presence + depth
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.dataflow import project_dfg, dataflow_vector
from code_shape.core.enriched_shape import enriched_shape


def _cosine(a, b):
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def call_depth_metrics(proj):
    """Longest + avg call chain depth (a->b->c = depth 2)."""
    adj = {}
    for a, b in proj.call_edges:
        adj.setdefault(a, set()).add(b)
    depths = {}
    for fn in proj.functions:
        # BFS from fn
        seen = {fn}
        queue = [(fn, 0)]
        maxd = 0
        while queue:
            node, d = queue.pop(0)
            maxd = max(maxd, d)
            for nb in adj.get(node, []):
                if nb not in seen:
                    seen.add(nb)
                    queue.append((nb, d + 1))
        depths[fn] = maxd
    if not depths:
        return 0.0, 0.0
    return max(depths.values()), sum(depths.values()) / len(depths)


def centrality(proj):
    """Max degree centrality (hub function)."""
    deg = {}
    for a, b in proj.call_edges:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    n = len(proj.functions)
    if not deg or n <= 1:
        return 0.0
    return max(deg.values()) / (n - 1)


def clustering(proj):
    """Avg clustering coefficient of the call graph."""
    adj = {}
    for a, b in proj.call_edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    if not adj:
        return 0.0
    total = 0.0
    for node, nbrs in adj.items():
        k = len(nbrs)
        if k < 2:
            continue
        links = sum(1 for x in nbrs for y in nbrs if x != y and y in adj.get(x, set()))
        total += (2 * links) / (k * (k - 1))
    return total / len(adj)


def dataflow_depth(proj):
    """Longest data-dependency chain within any function."""
    maxd = 0
    for fn, dfg in proj.functions.items():
        # build var dependency graph
        adj = {}
        for e in dfg.edges:
            adj.setdefault(e.src, set()).add(e.dst)
        for var in dfg.vars:
            seen = {var}
            queue = [(var, 0)]
            while queue:
                node, d = queue.pop(0)
                maxd = max(maxd, d)
                for nb in adj.get(node, []):
                    if nb not in seen:
                        seen.add(nb)
                        queue.append((nb, d + 1))
    return maxd


def candidate_dims(proj):
    """Compute all candidate dataflow-derived dimensions."""
    maxd, avgd = call_depth_metrics(proj)
    n = len(proj.functions)
    calls = len(proj.call_edges)
    return {
        "GRAPH:MAX_CALL_DEPTH": float(maxd),
        "GRAPH:AVG_CALL_DEPTH": round(avgd, 3),
        "GRAPH:COUPLING": round(calls / n, 3) if n else 0.0,
        "GRAPH:CENTRALITY": round(centrality(proj), 3),
        "GRAPH:CLUSTERING": round(clustering(proj), 3),
        "GRAPH:DATAFLOW_DEPTH": float(dataflow_depth(proj)),
        "GRAPH:PARAM_FANIN": round(sum(len(f.params) for f in proj.functions.values()) / n, 3) if n else 0.0,
        "GRAPH:RETURN_FANOUT": round(sum(len(f.returns) for f in proj.functions.values()) / n, 3) if n else 0.0,
    }


# ── Test: do candidate dims discriminate structure the histogram misses? ──
prog_a = '''
def f1(x):
    y = x + 1
    return y
def f2(a):
    b = a * 2
    return b
def main():
    r1 = f1(1)
    r2 = f2(2)
    return r1 + r2
'''
prog_b = '''
def f1(x):
    y = x + 1
    return y
def f2(a):
    b = f1(a)
    return b
def main():
    r = f2(5)
    return r
'''
prog_c = '''
def greet(name):
    msg = 'Hello ' + name
    print(msg)
def main():
    greet('world')
'''

print("=== Discrimination test: A vs B (similar hist, diff structure) ===")
ea, eb = enriched_shape(prog_a), enriched_shape(prog_b)
print(f"histogram cosine: {_cosine(ea, eb):.3f}  (should be HIGH, ~0.94)")
da, db = candidate_dims(project_dfg(prog_a)), candidate_dims(project_dfg(prog_b))
print(f"candidate-dims cosine: {_cosine(da, db):.3f}  (should be LOWER, discriminating)")
print("A dims:", da)
print("B dims:", db)

print("\n=== Discrimination test: A vs C (truly different) ===")
ec = enriched_shape(prog_c)
dc = candidate_dims(project_dfg(prog_c))
print(f"histogram cosine: {_cosine(ea, ec):.3f}")
print(f"candidate-dims cosine: {_cosine(da, dc):.3f}")

print("\n=== Which dims differ most between A and B? ===")
for k in da:
    if da[k] != db[k]:
        print(f"  {k}: A={da[k]} B={db[k]}")
