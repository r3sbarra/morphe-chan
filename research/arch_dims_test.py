"""Research: coupling/cohesion, architectural patterns, change-impact, and
dataflow-based bug detection — new dimensions/uses for the dataflow graph.

Explores NEW dimensions and USES beyond the histogram:
  1. COUPLING/COHESION — how tightly functions are coupled (architecture)
  2. ARCHITECTURAL PATTERNS — layered vs flat vs hub-and-spoke call structure
  3. CHANGE-IMPACT — which functions are affected by a change (fan-in closure)
  4. BUG DETECTION — use-before-assign, uninitialized vars, dead code
  5. DATAFLOW-BASED SIMILARITY for the 3D view (truthful representation)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.dataflow import project_dfg


# ── 1. COUPLING / COHESION ────────────────────────────────────────────────
def coupling_cohesion_dims(proj):
    """Coupling (inter-function) and cohesion (intra-function) metrics.

      ARCH:COUPLING_RATIO   — call edges / functions (how interconnected)
      ARCH:COHESION         — intra-file calls / total calls (1 = all internal)
      ARCH:LAYERED          — 1 if call graph is a DAG (no cycles, layered)
      ARCH:HUB_DEGREE       — max fan-out (hub function that calls many)
      ARCH:LEAF_RATIO       — fraction of functions that call nothing (leaves)
      ARCH:AVG_FANOUT       — mean functions called per function
    """
    n = len(proj.functions)
    if not n:
        return {}
    calls = len(proj.call_edges)
    fanout = {}
    for a, b in proj.call_edges:
        fanout[a] = fanout.get(a, 0) + 1
    leaves = sum(1 for f in proj.functions if f not in fanout)
    # layered = DAG (no cycles)
    layered = 1.0 if _is_dag(proj.call_edges) else 0.0
    return {
        "ARCH:COUPLING_RATIO": round(calls / n, 3),
        "ARCH:LAYERED": layered,
        "ARCH:HUB_DEGREE": max(fanout.values(), default=0),
        "ARCH:LEAF_RATIO": round(leaves / n, 3),
        "ARCH:AVG_FANOUT": round(sum(fanout.values()) / n, 3),
    }


def _is_dag(edges):
    """True if the call graph is a DAG (no cycles)."""
    adj = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
    visiting, visited = set(), set()

    def dfs(node):
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        for nb in adj.get(node, []):
            if not dfs(nb):
                return False
        visiting.remove(node)
        visited.add(node)
        return True

    for node in list(adj.keys()):
        if not dfs(node):
            return False
    return True


# ── 2. CHANGE-IMPACT ──────────────────────────────────────────────────────
def change_impact(proj, changed_fn):
    """Which functions are affected if `changed_fn` changes (fan-in closure).

    Returns the set of functions that transitively call `changed_fn` (they
    depend on it) — the impact set.
    """
    # reverse call graph: who calls whom
    callers = {}
    for a, b in proj.call_edges:
        callers.setdefault(b, set()).add(a)
    impacted = set()
    frontier = {changed_fn}
    while frontier:
        nxt = set()
        for f in frontier:
            for caller in callers.get(f, []):
                if caller not in impacted:
                    impacted.add(caller)
                    nxt.add(caller)
        frontier = nxt
    return impacted


# ── 3. BUG DETECTION via dataflow ──────────────────────────────────────────
def dataflow_bugs(proj):
    """Detect dataflow anomalies:
      - USE_BEFORE_ASSIGN: var read but never defined in the function
      - UNUSED_PARAM: param never used in any edge
      - DEAD_VAR: var defined but never read (no outgoing edges)
    """
    bugs = {"USE_BEFORE_ASSIGN": [], "UNUSED_PARAM": [], "DEAD_VAR": []}
    for fn, dfg in proj.functions.items():
        defined = set(dfg.vars.keys())
        read = {e.src for e in dfg.edges}
        # use-before-assign: read but not defined (and not a param)
        for e in dfg.edges:
            if e.src not in defined and e.src not in dfg.params and e.src not in ("return",):
                if e.src not in bugs["USE_BEFORE_ASSIGN"]:
                    bugs["USE_BEFORE_ASSIGN"].append(f"{fn}:{e.src}")
        # unused params
        used_params = {e.src for e in dfg.edges if e.src in dfg.params}
        for p in dfg.params:
            if p not in used_params:
                bugs["UNUSED_PARAM"].append(f"{fn}:{p}")
        # dead vars: defined but never read (no outgoing edges)
        for var in dfg.vars:
            if var not in read and var not in dfg.params:
                bugs["DEAD_VAR"].append(f"{fn}:{var}")
    return bugs


# ── Test programs ──────────────────────────────────────────────────────────
LAYERED = '''
def util_a(x):
    return x + 1
def util_b(x):
    return x * 2
def service(x):
    return util_a(util_b(x))
def main():
    return service(5)
'''

HUB = '''
def leaf1(x): return x
def leaf2(x): return x
def leaf3(x): return x
def hub(x):
    a = leaf1(x)
    b = leaf2(x)
    c = leaf3(x)
    return a + b + c
def main():
    return hub(1)
'''

BUGGY = '''
def calc(x):
    if x > 0:
        total = x * 2
    return total  # use-before-assign
def unused(y, z):
    return y  # z unused
def dead():
    temp = 5  # dead var
    return 1
'''


if __name__ == "__main__":
    print("=== COUPLING / COHESION / ARCHITECTURE ===")
    for name, code in [("layered", LAYERED), ("hub", HUB), ("buggy", BUGGY)]:
        proj = project_dfg(code)
        print(f"  {name}: {coupling_cohesion_dims(proj)}")

    print("\n=== CHANGE-IMPACT ===")
    proj = project_dfg(LAYERED)
    print("  layered: change util_a impacts:", change_impact(proj, "util_a"))
    print("  layered: change service impacts:", change_impact(proj, "service"))

    print("\n=== BUG DETECTION via dataflow ===")
    proj = project_dfg(BUGGY)
    print("  buggy:", dataflow_bugs(proj))
