"""Research: flow direction, flow intensity, and flow-algorithm correlation.

Explores whether the dataflow graph enables NEW dimensions around:
  1. FLOW DIRECTION — the direction data flows (param -> local -> call -> return)
  2. FLOW INTENSITY — how much data flows (fan-in/out, edge density, depth)
  3. FLOW-ALGORITHM CORRELATION — whether flow structure correlates with
     detected algorithms (binary search, sort, recursion, etc.)

These are dimensions the histogram cannot capture because it has no notion
of *direction* or *intensity* of data movement.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.dataflow import project_dfg
from code_shape.analysis.algorithm_detector import detect_algorithm


# ── 1. FLOW DIRECTION dimensions ───────────────────────────────────────────
def flow_direction_dims(proj):
    """Derive flow-direction dimensions from the DFG.

    Direction categories:
      PARAM->LOCAL   — params flowing into local vars (input processing)
      LOCAL->CALL    — locals flowing into function calls (data passed out)
      CALL->LOCAL    — call results flowing into locals (data received)
      LOCAL->RETURN  — locals flowing into returns (output)
      PARAM->RETURN  — params passed straight through (passthrough)
    """
    dims = {"FLOWDIR:PARAM_TO_LOCAL": 0, "FLOWDIR:LOCAL_TO_CALL": 0,
            "FLOWDIR:CALL_TO_LOCAL": 0, "FLOWDIR:LOCAL_TO_RETURN": 0,
            "FLOWDIR:PARAM_TO_RETURN": 0, "FLOWDIR:PASSTHROUGH": 0}
    for fn, dfg in proj.functions.items():
        params = set(dfg.params)
        locals_ = set(dfg.vars) - params
        for e in dfg.edges:
            if e.kind == "assign":
                if e.src in params and e.dst in locals_:
                    dims["FLOWDIR:PARAM_TO_LOCAL"] += 1
                elif e.src in locals_ and e.dst in locals_:
                    pass  # local->local, not a direction category
            elif e.kind == "call_arg":
                if e.src in locals_:
                    dims["FLOWDIR:LOCAL_TO_CALL"] += 1
                elif e.src in params:
                    dims["FLOWDIR:PARAM_TO_CALL"] = dims.get("FLOWDIR:PARAM_TO_CALL", 0) + 1
            elif e.kind == "return":
                if e.src in locals_:
                    dims["FLOWDIR:LOCAL_TO_RETURN"] += 1
                elif e.src in params:
                    dims["FLOWDIR:PARAM_TO_RETURN"] += 1
        # passthrough: param appears in return without local transform
        for r in dfg.returns:
            for p in params:
                if p in r and not any(e.src == p and e.dst in locals_ for e in dfg.edges):
                    dims["FLOWDIR:PASSTHROUGH"] += 1
    return dims


# ── 2. FLOW INTENSITY dimensions ───────────────────────────────────────────
def flow_intensity_dims(proj):
    """Derive flow-intensity dimensions.

      FLOWINT:EDGE_DENSITY   — data edges / (vars * functions)
      FLOWINT:MAX_FANIN      — max vars flowing into one var
      FLOWINT:MAX_FANOUT     — max vars flowing out of one var
      FLOWINT:AVG_CHAIN      — avg data-dependency chain length
      FLOWINT:PARAM_UTIL     — fraction of params actually used in flow
      FLOWINT:RETURN_DEPTH   — how deep the return value is (transforms before return)
    """
    total_vars = sum(len(f.vars) for f in proj.functions.values())
    total_edges = sum(len(f.edges) for f in proj.functions.values())
    n = len(proj.functions)
    dims = {
        "FLOWINT:EDGE_DENSITY": round(total_edges / max(total_vars, 1), 3),
        "FLOWINT:MAX_FANIN": 0, "FLOWINT:MAX_FANOUT": 0,
        "FLOWINT:AVG_CHAIN": 0, "FLOWINT:PARAM_UTIL": 0, "FLOWINT:RETURN_DEPTH": 0,
    }
    # fan-in/out per var
    fanin, fanout = {}, {}
    for fn, dfg in proj.functions.items():
        for e in dfg.edges:
            fanout[e.src] = fanout.get(e.src, 0) + 1
            fanin[e.dst] = fanin.get(e.dst, 0) + 1
    dims["FLOWINT:MAX_FANIN"] = max(fanin.values(), default=0)
    dims["FLOWINT:MAX_FANOUT"] = max(fanout.values(), default=0)
    # param utilization
    used_params = 0
    total_params = 0
    for fn, dfg in proj.functions.items():
        total_params += len(dfg.params)
        used = set()
        for e in dfg.edges:
            if e.src in dfg.params:
                used.add(e.src)
        used_params += len(used)
    dims["FLOWINT:PARAM_UTIL"] = round(used_params / max(total_params, 1), 3)
    # return depth: how many transforms between param and return
    depths = []
    for fn, dfg in proj.functions.items():
        for r in dfg.returns:
            # count edges in the chain feeding the return
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


# ── 3. FLOW-ALGORITHM CORRELATION ──────────────────────────────────────────
def flow_algorithm_correlation(code):
    """Test whether flow structure correlates with detected algorithms.

    Hypothesis: algorithms with distinctive flow (binary search = param->local
    with loop, sort = call to sorted) should have distinctive flow dims.
    """
    proj = project_dfg(code)
    algs = detect_algorithm(code, "python")
    alg_names = [a["algorithm"] for a in algs]
    fd = flow_direction_dims(proj)
    fi = flow_intensity_dims(proj)
    return {
        "algorithms": alg_names,
        "flow_direction": fd,
        "flow_intensity": fi,
    }


# ── Test programs ──────────────────────────────────────────────────────────
BINARY_SEARCH = '''
def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
'''

SORT = '''
def sort_and_search(data, target):
    sorted_data = sorted(data)
    return binary_search(sorted_data, target)
'''

SIMPLE = '''
def add(a, b):
    return a + b
'''

if __name__ == "__main__":
    print("=== FLOW DIRECTION dims ===")
    for name, code in [("binary_search", BINARY_SEARCH), ("sort", SORT), ("simple", SIMPLE)]:
        proj = project_dfg(code)
        print(f"  {name}: {flow_direction_dims(proj)}")

    print("\n=== FLOW INTENSITY dims ===")
    for name, code in [("binary_search", BINARY_SEARCH), ("sort", SORT), ("simple", SIMPLE)]:
        proj = project_dfg(code)
        print(f"  {name}: {flow_intensity_dims(proj)}")

    print("\n=== FLOW-ALGORITHM CORRELATION ===")
    for name, code in [("binary_search", BINARY_SEARCH), ("sort", SORT), ("simple", SIMPLE)]:
        r = flow_algorithm_correlation(code)
        print(f"  {name}: algs={r['algorithms']} dir={r['flow_direction']} int={r['flow_intensity']}")
