#!/usr/bin/env python
"""self_derive_anomaly.py — NEW derived capability: geometric anomaly detection
on Morphe-chan's enriched shape space.

Idea (self-derived): the enriched shape space is low-dimensional (~6-9 global
intrinsic dims) and unit-sphere. A function whose shape vector is a geometric
OUTLIER (far from the centroid / cluster) is structurally exceptional → a
candidate code smell / unusual logic / bug. This gives a novel, shape-native
"anomaly score" not present in Morphe-chan today.

Applies it to Morphe-chan's OWN source (analyzing itself): embed all function-ish
snippets of src/code_shape, compute distance-to-centroid on the PRIM:* subspace
(the language-invariant clone-sensitive core), and report the most anomalous
functions as candidates.
"""
import sys, os, glob, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from code_shape.core.enriched_shape import enriched_shape


def prim_proj(code, lang="python"):
    """PRIM:* subspace vector (language-invariant core)."""
    s = enriched_shape(code, lang)
    p = {k: v for k, v in s.items() if k.startswith("PRIM:") and v not in (0, 0.0)}
    n = math.sqrt(sum(v * v for v in p.values()))
    return {k: v / n for k, v in p.items()} if n else p


def main():
    # Collect function bodies from Morphe-chan's own source via a simple
    # function-splitting heuristic (one-line-aware).
    src_root = 'src/code_shape'
    functions = []
    for path in sorted(glob.glob(os.path.join(src_root, '**', '*.py'), recursive=True)):
        try:
            text = open(path).read()
        except Exception:
            continue
        # naive top-level def extraction (single-line bodies + multiline)
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            l = lines[i]
            s = l.strip()
            if s.startswith("def ") or s.startswith("    def "):
                # collect until dedent (rough)
                sig = l
                body_lines = [l]
                j = i + 1
                base_indent = len(l) - len(l.lstrip())
                while j < len(lines):
                    nl = lines[j]
                    if nl.strip() and len(nl) - len(nl.lstrip()) <= base_indent:
                        break
                    body_lines.append(nl)
                    j += 1
                full = "\n".join(body_lines)
                if 5 < len(full) < 1500:
                    functions.append((os.path.basename(path), sig.strip(), full))
                i = j
                continue
            i += 1

    print(f"extracted {len(functions)} functions from {src_root}")

    # embed all on PRIM:* subspace
    vecs = []
    skipped = 0
    for path, sig, code in functions:
        try:
            v = prim_proj(code)
            if v:
                vecs.append((path, sig, v))
            else:
                skipped += 1
        except Exception:
            skipped += 1
    print(f"embedded {len(vecs)} (skipped {skipped})")

    # centroid + per-point distance (angular distance on unit sphere)
    keys = set(k for _, _, v in vecs for k in v)
    n = len(vecs)
    center = {k: sum(v.get(k, 0.0) for _, _, v in vecs) / n for k in keys}
    def dist(p):
        # chordal distance to centroid (0=identical direction, high=outlier)
        return math.sqrt(sum((p.get(k, 0.0) - center[k]) ** 2 for k in keys))

    scored = [(round(dist(v), 3), path, sig) for path, sig, v in vecs]
    scored.sort(reverse=True)

    print("\n=== most anomalous functions (by PRIM-space deviation from centroid) ===")
    for d, path, sig in scored[:12]:
        print(f"  {d:5.3f}  {path:28s} {sig[:55]}")

    # stats
    import statistics
    ds = [s[0] for s in scored]
    mu = statistics.mean(ds)
    sd = statistics.stdev(ds) if len(ds) > 1 else 0
    thresh = mu + 2 * sd
    outliers = [s for s in scored if s[0] > thresh]
    print(f"\nmean={mu:.3f} sd={sd:.3f}  -> outlier threshold (μ+2σ)={thresh:.3f}: {len(outliers)} outliers")


if __name__ == "__main__":
    main()
