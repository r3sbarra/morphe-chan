#!/usr/bin/env python
"""code_shape/memory.py — Shape Memory: snapshot & cascading-change tracker.

Morphē-chan keeps a local memory of code shapes over time so she can detect
the **cascading effects** of code changes — dimension shifts, gained/lost
algorithms & patterns, new or fixed vulnerabilities, complexity class changes.

Storage layout (inside the *analyzed project*, gitignored):
    .morphe_snapshots/
        <slug>.jsonl          <- line-delimited JSON, one record per snapshot
                                 oldest first; trimmed to HISTORY_LIMIT lines.

Dependency-free (stdlib only).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Constants ──────────────────────────────────────────────────────────────
SNAPSHOT_DIR_NAME = ".morphe_snapshots"
HISTORY_LIMIT = int(os.environ.get("MORPHE_SNAPSHOT_HISTORY", "5"))

_COMPLEXITY_ORDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"]


# ── Data Models ────────────────────────────────────────────────────────────
@dataclass
class ShapeSnapshot:
    """A frozen snapshot of a target's shape at a point in time."""
    target: str
    timestamp: str
    shape: Optional[str] = None
    structural: Optional[str] = None
    complexity: Optional[str] = None
    enriched: Dict[str, float] = field(default_factory=dict)
    composite: Dict[str, float] = field(default_factory=dict)
    algorithms: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    vuln_types: List[str] = field(default_factory=list)
    type_profile: Dict[str, float] = field(default_factory=dict)
    type_flow: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ShapeSnapshot":
        return ShapeSnapshot(
            target=d.get("target", ""),
            timestamp=d.get("timestamp", ""),
            shape=d.get("shape"),
            structural=d.get("structural"),
            complexity=d.get("complexity"),
            enriched=d.get("enriched", {}),
            composite=d.get("composite", {}),
            algorithms=d.get("algorithms", []),
            patterns=d.get("patterns", []),
            vuln_types=d.get("vuln_types", []),
            type_profile=d.get("type_profile", {}),
            type_flow=d.get("type_flow", {}),
        )


@dataclass
class DimDelta:
    """A change in a single shape dimension."""
    dim: str
    old_val: float
    new_val: float
    delta: float
    pct_change: float


@dataclass
class ShapeDiff:
    """The cascading diff between two snapshots."""
    target: str
    old_timestamp: str
    new_timestamp: str

    vector_delta: List[DimDelta] = field(default_factory=list)

    complexity_changed: bool = False
    old_complexity: Optional[str] = None
    new_complexity: Optional[str] = None
    complexity_direction: str = "same"

    algorithms_gained: List[str] = field(default_factory=list)
    algorithms_lost: List[str] = field(default_factory=list)
    patterns_gained: List[str] = field(default_factory=list)
    patterns_lost: List[str] = field(default_factory=list)
    vulns_gained: List[str] = field(default_factory=list)
    vulns_fixed: List[str] = field(default_factory=list)

    # type-flow cascade (NEW): variable/param type changes + cross-function flow
    type_changes: List[Dict[str, Any]] = field(default_factory=list)
    type_flow_changed: bool = False
    type_flow_propagations: int = 0
    type_flow_errors: int = 0

    cascade_score: float = 0.0
    cascade_verdict: str = ""

    @property
    def has_changes(self) -> bool:
        return bool(
            self.vector_delta or self.complexity_changed
            or self.algorithms_gained or self.algorithms_lost
            or self.patterns_gained or self.patterns_lost
            or self.vulns_gained or self.vulns_fixed
        )

    def top_changed_dims(self, n: int = 8) -> List[DimDelta]:
        return sorted(self.vector_delta, key=lambda d: abs(d.delta), reverse=True)[:n]


# ── Diff engine ────────────────────────────────────────────────────────────
def _complexity_direction(old: Optional[str], new: Optional[str]) -> str:
    if not old or not new or old == new:
        return "same"
    try:
        oi, ni = _COMPLEXITY_ORDER.index(old), _COMPLEXITY_ORDER.index(new)
    except ValueError:
        return "same"
    if ni < oi:
        return "improved"
    if ni > oi:
        return "degraded"
    return "same"


def _cascade_verdict(score: float, diff: ShapeDiff) -> str:
    if not diff.has_changes and not diff.type_changes:
        return "(◕‿◕✿) No shape changes detected, senpai! Geometry is stable! ✦"
    if diff.vulns_gained:
        return f"(⊙_⊙) Yikes! {len(diff.vulns_gained)} new vuln(s) appeared in the shape! Fix it, senpai!"
    if diff.complexity_direction == "degraded":
        return f"(>.<) Complexity degraded: {diff.old_complexity} -> {diff.new_complexity}! Careful, senpai!"
    if diff.complexity_direction == "improved":
        return f"(◕‿◕✿) Complexity improved: {diff.old_complexity} -> {diff.new_complexity}! Great shape, senpai! ✦"
    if diff.vulns_fixed:
        return f"(≧◡≦) {len(diff.vulns_fixed)} vuln(s) fixed! Shape is getting cleaner, senpai! ✦"
    if diff.type_flow_errors > 0:
        return f"(⊙△⊙) {diff.type_flow_errors} cross-function type error(s) appeared — cascade alert, senpai!"
    if diff.type_flow_changed:
        return f"(◕‿◕) Type flow shifted across functions ({diff.type_flow_propagations} propagations) — cascading, senpai~"
    if score > 0.5:
        return f"(⊙△⊙) Major shape shift! {len(diff.vector_delta)} dims changed — cascade alert, senpai!"
    if score > 0.2:
        return f"(◕‿◕) Moderate shape change ({len(diff.vector_delta)} dims). Geometry is evolving, senpai~"
    return f"(◕‿◕✿) Minor shape tweak ({len(diff.vector_delta)} dim(s)). Looking good, senpai! ✦"


def diff_snapshots(old: ShapeSnapshot, new: ShapeSnapshot) -> ShapeDiff:
    """Compute a ShapeDiff from two snapshots."""
    diff = ShapeDiff(
        target=new.target,
        old_timestamp=old.timestamp,
        new_timestamp=new.timestamp,
    )

    old_vec = old.enriched or old.composite
    new_vec = new.enriched or new.composite
    all_dims = set(old_vec) | set(new_vec)
    deltas: List[DimDelta] = []
    for dim in all_dims:
        ov, nv = old_vec.get(dim, 0.0), new_vec.get(dim, 0.0)
        delta = nv - ov
        if abs(delta) > 1e-9:
            pct = (delta / ov * 100) if ov else 0.0
            deltas.append(DimDelta(dim=dim, old_val=ov, new_val=nv, delta=delta, pct_change=pct))
    diff.vector_delta = sorted(deltas, key=lambda d: abs(d.delta), reverse=True)

    if old.complexity != new.complexity and (old.complexity or new.complexity):
        diff.complexity_changed = True
        diff.old_complexity = old.complexity
        diff.new_complexity = new.complexity
        diff.complexity_direction = _complexity_direction(old.complexity, new.complexity)

    old_algs, new_algs = set(old.algorithms), set(new.algorithms)
    diff.algorithms_gained = sorted(new_algs - old_algs)
    diff.algorithms_lost = sorted(old_algs - new_algs)

    old_pats, new_pats = set(old.patterns), set(new.patterns)
    diff.patterns_gained = sorted(new_pats - old_pats)
    diff.patterns_lost = sorted(old_pats - new_pats)

    old_vulns, new_vulns = set(old.vuln_types), set(new.vuln_types)
    diff.vulns_gained = sorted(new_vulns - old_vulns)
    diff.vulns_fixed = sorted(old_vulns - new_vulns)

    # ── Type-flow cascade (NEW) ────────────────────────────────────────────
    # Compare type profiles: which type buckets gained/lost weight?
    old_tp, new_tp = old.type_profile or {}, new.type_profile or {}
    all_tp = set(old_tp) | set(new_tp)
    type_changes = []
    for dim in all_tp:
        ov, nv = old_tp.get(dim, 0.0), new_tp.get(dim, 0.0)
        if abs(nv - ov) > 1e-9:
            type_changes.append({"dim": dim, "old": ov, "new": nv, "delta": nv - ov})
    diff.type_changes = sorted(type_changes, key=lambda d: abs(d["delta"]), reverse=True)

    # Did the cross-function type flow change? (propagations / type errors)
    old_flow = old.type_flow or {}
    new_flow = new.type_flow or {}
    old_prop = old_flow.get("propagations", 0)
    new_prop = new_flow.get("propagations", 0)
    old_err = old_flow.get("type_errors", 0)
    new_err = new_flow.get("type_errors", 0)
    diff.type_flow_changed = (old_prop != new_prop) or (old_err != new_err)
    diff.type_flow_propagations = new_prop
    diff.type_flow_errors = new_err

    total_dims = max(len(all_dims), 1)
    changed_dims = len(diff.vector_delta)
    categorical_events = (
        len(diff.algorithms_gained) + len(diff.algorithms_lost)
        + len(diff.patterns_gained) + len(diff.patterns_lost)
        + len(diff.vulns_gained) + len(diff.vulns_fixed)
        + (2 if diff.complexity_changed else 0)
    )
    dim_score = min(changed_dims / total_dims, 1.0)
    cat_score = min(categorical_events / 10.0, 1.0)
    # type-flow cascade: type changes + flow changes are a strong signal
    type_score = min(len(diff.type_changes) / 8.0, 1.0)
    flow_score = 1.0 if diff.type_flow_changed else 0.0
    diff.cascade_score = round(
        0.45 * dim_score + 0.25 * cat_score + 0.2 * type_score + 0.1 * flow_score, 3
    )
    diff.cascade_verdict = _cascade_verdict(diff.cascade_score, diff)

    return diff


# ── SnapshotStore ──────────────────────────────────────────────────────────
def _slug(target: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_\-.]", "_", str(target))
    clean = re.sub(r"_+", "_", clean).strip("_")
    h = hashlib.sha1(target.encode()).hexdigest()[:8]
    return f"{clean[:40]}_{h}"


class SnapshotStore:
    """Persist ShapeSnapshots to a .morphe_snapshots/ directory."""

    def __init__(self, root_dir: Path, history: int = HISTORY_LIMIT):
        self.root = root_dir / SNAPSHOT_DIR_NAME
        self.history = history
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_gitignore(root_dir)

    @staticmethod
    def _ensure_gitignore(project_root: Path) -> None:
        gi = project_root / ".gitignore"
        marker = ".morphe_snapshots/"
        if gi.exists():
            text = gi.read_text(encoding="utf-8")
            if marker in text:
                return
            gi.write_text(
                text.rstrip("\n") + f"\n\n# Morphe-chan shape memory (local only)\n{marker}\n",
                encoding="utf-8",
            )
        else:
            gi.write_text(f"# Morphe-chan shape memory (local only)\n{marker}\n", encoding="utf-8")

    def _path(self, target: str) -> Path:
        return self.root / f"{_slug(target)}.jsonl"

    def save(self, snap: ShapeSnapshot) -> None:
        p = self._path(snap.target)
        existing: List[Dict[str, Any]] = []
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        existing.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        existing.append(snap.to_dict())
        existing = existing[-self.history:]
        p.write_text("\n".join(json.dumps(r) for r in existing) + "\n", encoding="utf-8")

    def load_latest(self, target: str) -> Optional[ShapeSnapshot]:
        p = self._path(target)
        if not p.exists():
            return None
        lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return None
        try:
            return ShapeSnapshot.from_dict(json.loads(lines[-1]))
        except (json.JSONDecodeError, KeyError):
            return None

    def load_all(self, target: str) -> List[ShapeSnapshot]:
        p = self._path(target)
        if not p.exists():
            return []
        snaps = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    snaps.append(ShapeSnapshot.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    pass
        return snaps

    def list_targets(self) -> List[str]:
        targets = []
        for f in sorted(self.root.glob("*.jsonl")):
            lines = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                try:
                    targets.append(json.loads(lines[0]).get("target", f.stem))
                except json.JSONDecodeError:
                    pass
        return targets


# ── Snapshot builder ───────────────────────────────────────────────────────
def snapshot_from_report(rep: Any) -> ShapeSnapshot:
    """Build a ShapeSnapshot from an AnalysisReport (duck-typed)."""
    # type profile + flow from the report's source code (if available)
    type_profile = {}
    type_flow = {}
    code = getattr(rep, "code", None) or getattr(rep, "source", None)
    lang = getattr(rep, "lang", "python") or "python"
    if code:
        try:
            from code_shape.core.variable_shape import type_profile as _tp, cascading_type_flow as _cf
            type_profile = _tp(code, lang)
            type_flow = _cf(code, lang)
        except Exception:
            pass
    return ShapeSnapshot(
        target=rep.target,
        timestamp=rep.timestamp,
        shape=rep.shape,
        structural=getattr(rep, "structural", None),
        complexity=rep.complexity,
        enriched=dict(rep.enriched) if rep.enriched else {},
        composite=dict(rep.composite) if rep.composite else {},
        algorithms=[a.get("algorithm", "") for a in (rep.algorithms or [])],
        patterns=[p.get("pattern", "") for p in (rep.patterns or [])],
        vuln_types=list({
            v.get("type", "") for v in (rep.vulnerabilities or []) if v.get("type")
        }),
        type_profile=type_profile,
        type_flow=type_flow,
    )


def snapshot_and_diff(rep: Any, project_root: Path) -> Optional[ShapeDiff]:
    """Save a snapshot from rep and return diff vs. previous snapshot.

    Returns None on first run (no previous snapshot exists).
    """
    store = SnapshotStore(project_root)
    new_snap = snapshot_from_report(rep)
    old_snap = store.load_latest(rep.target)
    store.save(new_snap)
    if old_snap is None:
        return None
    return diff_snapshots(old_snap, new_snap)


# ── CLI diff renderer ──────────────────────────────────────────────────────
def format_diff_cli(diff: ShapeDiff) -> str:
    """Render a ShapeDiff as a compact CLI block."""
    bar = "━" * 63
    lines = [
        "",
        f"╔{bar}╗",
        f"║  ⬡ Morphe-chan Cascading Shape Diff  cascade score: {diff.cascade_score:.2f}   ║",
        f"╚{bar}╝",
        f"   {diff.cascade_verdict}",
        f"   Prev : {diff.old_timestamp}",
        f"   Now  : {diff.new_timestamp}",
        "",
    ]

    if diff.complexity_changed:
        icon = "⚡ DEGRADED" if diff.complexity_direction == "degraded" else "⚡ IMPROVED"
        lines += [
            f"  {icon}: {diff.old_complexity or 'n/a'} -> {diff.new_complexity or 'n/a'}",
            "",
        ]

    top = diff.top_changed_dims(8)
    if top:
        lines.append("  Top changed dimensions:")
        for d in top:
            sign = "+" if d.delta > 0 else ""
            arrow = "^" if d.delta > 0 else "v"
            lines.append(f"    {arrow}  {d.dim:<28s}  {sign}{d.delta:+.3f}  (was {d.old_val:.3f})")
        lines.append("")

    for label, gained, lost in [
        ("Algorithms", diff.algorithms_gained, diff.algorithms_lost),
        ("Patterns",   diff.patterns_gained,   diff.patterns_lost),
        ("Vulns",      diff.vulns_gained,       diff.vulns_fixed),
    ]:
        if gained or lost:
            lines.append(f"  {label}:")
            for g in gained:
                lines.append(f"    + {g}")
            for lo in lost:
                lines.append(f"    - {lo}")
            lines.append("")

    if diff.type_changes:
        lines.append("  Type-flow cascade:")
        for tc in diff.type_changes[:6]:
            lines.append(f"    ~ {tc['dim']:<24s} {tc['delta']:+.1f}  (was {tc['old']:.1f})")
        if diff.type_flow_changed:
            lines.append(f"    ⚡ cross-function type flow changed "
                         f"(propagations={diff.type_flow_propagations}, "
                         f"type_errors={diff.type_flow_errors})")
        lines.append("")

    lines.append(f"╔{bar}╗")
    lines.append(f"╚{bar}╝")
    return "\n".join(lines)
