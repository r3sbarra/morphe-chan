"""test_memory.py — Tests for code_shape.memory (snapshot & cascading diff).

Verifies:
  1. ShapeSnapshot round-trips through to_dict/from_dict correctly.
  2. SnapshotStore save/load_latest/load_all work correctly.
  3. SnapshotStore respects HISTORY_LIMIT (trims oldest).
  4. diff_snapshots returns cascade_score=0 for identical snapshots.
  5. diff_snapshots detects complexity_changed correctly.
  6. diff_snapshots detects vulns_gained/vulns_fixed correctly.
  7. diff_snapshots detects algorithms/patterns gained/lost.
  8. format_diff_cli returns a non-empty string.
  9. snapshot_and_diff returns None on first run, ShapeDiff on second.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.memory import (
    ShapeSnapshot, SnapshotStore, ShapeDiff, DimDelta,
    diff_snapshots, snapshot_and_diff, format_diff_cli,
    snapshot_from_report,
)


# ── Fixtures ───────────────────────────────────────────────────────────────
def _snap(target="test", complexity="O(n)", algs=None, pats=None, vulns=None, enriched=None):
    return ShapeSnapshot(
        target=target,
        timestamp="2026-01-01T00:00:00",
        shape="READ>TRANSFORM>RETURN",
        complexity=complexity,
        enriched=enriched or {"PRIM:LOOP": 1.0, "EFF:NESTING": 1.0, "PRIM:RETURN": 1.0},
        algorithms=algs or [],
        patterns=pats or [],
        vuln_types=vulns or [],
    )


# ── 1. Round-trip ─────────────────────────────────────────────────────────
def test_snapshot_roundtrip():
    snap = _snap(algs=["binary_search"], pats=["singleton"], vulns=["sql_injection"])
    d = snap.to_dict()
    snap2 = ShapeSnapshot.from_dict(d)
    assert snap2.target == snap.target
    assert snap2.complexity == snap.complexity
    assert snap2.algorithms == snap.algorithms
    assert snap2.patterns == snap.patterns
    assert snap2.vuln_types == snap.vuln_types
    assert snap2.enriched == snap.enriched


# ── 2. SnapshotStore save / load_latest ───────────────────────────────────
def test_store_save_load():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = SnapshotStore(root, history=5)
        snap = _snap(target="myfile.py")
        store.save(snap)
        loaded = store.load_latest("myfile.py")
        assert loaded is not None
        assert loaded.target == "myfile.py"
        assert loaded.complexity == snap.complexity


# ── 3. History limit ─────────────────────────────────────────────────────
def test_snapshot_store_history():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = SnapshotStore(root, history=5)
        for i in range(6):
            snap = ShapeSnapshot(
                target="hist_test",
                timestamp=f"2026-01-0{i+1}T00:00:00",
                complexity="O(n)",
            )
            store.save(snap)
        all_snaps = store.load_all("hist_test")
        assert len(all_snaps) == 5, f"Expected 5, got {len(all_snaps)}"
        # Oldest should be from day 2 (day 1 was trimmed)
        assert "2026-01-02" in all_snaps[0].timestamp


# ── 4. diff identical snapshots => score = 0 ─────────────────────────────
def test_diff_no_change():
    snap = _snap()
    diff = diff_snapshots(snap, snap)
    assert diff.cascade_score == 0.0
    assert not diff.has_changes
    assert diff.complexity_direction == "same"


# ── 5. Complexity shift detected ─────────────────────────────────────────
def test_diff_complexity_shift():
    old = _snap(complexity="O(1)")
    new = _snap(complexity="O(n^2)")
    diff = diff_snapshots(old, new)
    assert diff.complexity_changed is True
    assert diff.old_complexity == "O(1)"
    assert diff.new_complexity == "O(n^2)"
    assert diff.complexity_direction == "degraded"
    assert diff.cascade_score > 0

def test_diff_complexity_improved():
    old = _snap(complexity="O(n^2)")
    new = _snap(complexity="O(n)")
    diff = diff_snapshots(old, new)
    assert diff.complexity_changed is True
    assert diff.complexity_direction == "improved"


# ── 6. Vulns gained / fixed ───────────────────────────────────────────────
def test_diff_vuln_gained():
    old = _snap(vulns=[])
    new = _snap(vulns=["sql_injection"])
    diff = diff_snapshots(old, new)
    assert "sql_injection" in diff.vulns_gained
    assert diff.vulns_fixed == []
    # Verdict should mention the vuln
    assert "vuln" in diff.cascade_verdict.lower()

def test_diff_vuln_fixed():
    old = _snap(vulns=["xss", "sql_injection"])
    new = _snap(vulns=[])
    diff = diff_snapshots(old, new)
    assert set(diff.vulns_fixed) == {"xss", "sql_injection"}
    assert diff.vulns_gained == []


# ── 7. Algorithms / patterns gained & lost ───────────────────────────────
def test_diff_algorithms_gained_lost():
    old = _snap(algs=["bubble_sort"])
    new = _snap(algs=["binary_search"])
    diff = diff_snapshots(old, new)
    assert "binary_search" in diff.algorithms_gained
    assert "bubble_sort" in diff.algorithms_lost

def test_diff_patterns():
    old = _snap(pats=["singleton"])
    new = _snap(pats=["singleton", "factory"])
    diff = diff_snapshots(old, new)
    assert "factory" in diff.patterns_gained
    assert diff.patterns_lost == []


# ── 8. Vector delta ──────────────────────────────────────────────────────
def test_diff_vector_delta():
    old = _snap(enriched={"PRIM:LOOP": 1.0, "EFF:NESTING": 2.0})
    new = _snap(enriched={"PRIM:LOOP": 1.0, "EFF:NESTING": 5.0, "EFF:RECURSION": 1.0})
    diff = diff_snapshots(old, new)
    dims = {d.dim: d for d in diff.vector_delta}
    assert "EFF:NESTING" in dims
    assert dims["EFF:NESTING"].delta == 3.0
    assert "EFF:RECURSION" in dims
    assert dims["EFF:RECURSION"].delta == 1.0


# ── 9. format_diff_cli ───────────────────────────────────────────────────
def test_format_diff_cli():
    old = _snap(complexity="O(1)", vulns=[])
    new = _snap(complexity="O(n^2)", vulns=["rce"], enriched={"PRIM:LOOP": 3.0, "EFF:NESTING": 3.0, "PRIM:RETURN": 1.0})
    diff = diff_snapshots(old, new)
    out = format_diff_cli(diff)
    assert len(out) > 50
    assert "cascade score" in out.lower() or "cascade" in out.lower()


# ── 10. snapshot_and_diff (first run = None, second = ShapeDiff) ─────────
def test_snapshot_and_diff_flow():
    """Duck-typed mock AnalysisReport."""
    class MockRep:
        target = "mock_target"
        timestamp = "2026-01-01T00:00:01"
        shape = "READ>RETURN"
        structural = None
        complexity = "O(n)"
        enriched = {"PRIM:LOOP": 1.0}
        composite = {}
        algorithms = [{"algorithm": "linear_search"}]
        patterns = []
        vulnerabilities = []

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rep = MockRep()

        # First call: no prior snapshot
        result = snapshot_and_diff(rep, root)
        assert result is None

        # Second call: diff exists
        rep.timestamp = "2026-01-01T00:00:02"
        rep.enriched = {"PRIM:LOOP": 3.0}   # big loop increase
        result = snapshot_and_diff(rep, root)
        assert result is not None
        assert result.cascade_score > 0


# ── Type-flow cascade ──────────────────────────────────────────────────────
def test_diff_detects_type_changes():
    """diff_snapshots detects variable/param type changes via type_profile."""
    old = _snap()
    old.type_profile = {"TYPE_PROFILE:LIST": 2.0, "TYPE_PROFILE:UNKNOWN": 1.0}
    new = _snap()
    new.type_profile = {"TYPE_PROFILE:DICT": 2.0, "TYPE_PROFILE:UNKNOWN": 1.0}
    diff = diff_snapshots(old, new)
    assert any(tc["dim"] == "TYPE_PROFILE:LIST" for tc in diff.type_changes)
    assert any(tc["dim"] == "TYPE_PROFILE:DICT" for tc in diff.type_changes)


def test_diff_detects_type_flow_change():
    """diff_snapshots flags cross-function type flow changes."""
    old = _snap()
    old.type_flow = {"propagations": 0, "type_errors": 0}
    new = _snap()
    new.type_flow = {"propagations": 2, "type_errors": 1}
    diff = diff_snapshots(old, new)
    assert diff.type_flow_changed is True
    assert diff.type_flow_propagations == 2
    assert diff.type_flow_errors == 1


def test_snapshot_from_report_populates_type_flow():
    """snapshot_from_report extracts type_profile + type_flow from source code."""
    class MockRep:
        target = "mock"
        timestamp = "2026-01-01T00:00:00"
        shape = "READ>RETURN"
        structural = None
        complexity = "O(n)"
        enriched = {"PRIM:LOOP": 1.0}
        composite = {}
        algorithms = []
        patterns = []
        vulnerabilities = []
        code = "def helper(items):\n    return len(items)\ndef main(data):\n    return helper(data)"
        lang = "python"

    snap = snapshot_from_report(MockRep())
    assert snap.type_profile  # non-empty
    assert "TYPE_PROFILE:LIST" in snap.type_profile
    assert snap.type_flow  # non-empty
    assert "functions" in snap.type_flow


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
