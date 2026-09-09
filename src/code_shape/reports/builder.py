#!/usr/bin/env python
"""reports/builder.py — Collect analysis data and build report artifacts.

The `AnalysisReport` dataclass holds every dimension the analysis produced,
plus metadata (timestamp, analysis type, target, tool versions). `build_report`
writes both a Markdown and an interactive HTML report into a dated, typed
folder under the project `reports/` root.

Layout:
    reports/<YYYY-MM-DD>/<analysis_type>/report.md
    reports/<YYYY-MM-DD>/<analysis_type>/report.html

Dependency-free (stdlib only). Chart.js is vendored locally for offline graphs.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Project reports root (repo-relative: <repo>/reports)
REPORT_ROOT = Path(__file__).resolve().parents[3] / "reports"


@dataclass
class AnalysisReport:
    """A single analysis report with all collected dimensions."""

    analysis_type: str            # e.g. "enriched", "project", "vulns"
    target: str                   # code snippet label or project path
    timestamp: str                # ISO timestamp
    date: str                     # YYYY-MM-DD
    language: Optional[str] = None

    # shape / enriched
    shape: Optional[str] = None
    structural: Optional[str] = None
    enriched: Dict[str, float] = field(default_factory=dict)

    # efficiency
    efficiency: Dict[str, Any] = field(default_factory=dict)
    complexity: Optional[str] = None

    # value flow
    value_flow: Dict[str, float] = field(default_factory=dict)
    flow_path: Optional[str] = None

    # detections
    algorithms: List[Dict[str, Any]] = field(default_factory=list)
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    sinks: List[str] = field(default_factory=list)

    # project-level
    composite: Dict[str, float] = field(default_factory=dict)
    imports: Dict[str, Any] = field(default_factory=dict)
    file_count: int = 0
    function_count: int = 0
    connection_count: int = 0

    # raw code (truncated) for context
    code_snippet: Optional[str] = None

    # extra free-form sections (e.g. synthesis output, compare results)
    extra: Dict[str, Any] = field(default_factory=dict)

    # cascading shape diff vs. previous snapshot (None = first run)
    shape_diff: Optional[Any] = None

    # ── helpers ────────────────────────────────────────────────────────────
    def output_dir(self) -> Path:
        """The dated, typed folder for this report."""
        return REPORT_ROOT / self.date / self.analysis_type

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save_json(self) -> Path:
        """Persist the raw data as JSON alongside the rendered reports."""
        d = self.output_dir()
        d.mkdir(parents=True, exist_ok=True)
        p = d / "data.json"
        p.write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")
        return p


def _now() -> datetime:
    return datetime.now()


def collect_analysis(
    analysis_type: str,
    target: str,
    code: Optional[str] = None,
    lang: Optional[str] = None,
    project_dir: Optional[str] = None,
) -> AnalysisReport:
    """Run the full analysis pipeline and collect every dimension.

    This is the single entry point used by the CLI `--report` flag. It gathers
    shape, enriched vector, efficiency, value-flow, algorithms, patterns,
    vulnerabilities, and (for project targets) the composite vector + imports.
    """
    from code_shape.core.code_shape_core import shape as _shape
    from code_shape.core.enriched_shape import enriched_shape
    from code_shape.core.structural_shape import structural_signature
    from code_shape.analysis.efficiency_shape import efficiency_summary
    from code_shape.analysis.enriched_efficiency import enriched_efficiency
    from code_shape.core.value_flow_shape import value_flow_shape, flow_path
    from code_shape.analysis.algorithm_detector import detect_algorithm
    from code_shape.analysis.pattern_detector import detect_patterns
    from code_shape.security.precise_issues import find_precise_issues, find_buffer_overflows
    from code_shape.security.vuln_v2 import detect_vulns_v2
    from code_shape.security.semantic_sinks import detect_sinks

    now = _now()
    rep = AnalysisReport(
        analysis_type=analysis_type,
        target=target,
        timestamp=now.isoformat(timespec="seconds"),
        date=now.strftime("%Y-%m-%d"),
        language=lang,
    )

    if code is not None:
        rep.code_snippet = code[:2000]
        try:
            rep.shape = _shape(code, lang)
        except Exception:
            rep.shape = None
        try:
            rep.structural = structural_signature(code)
        except Exception:
            rep.structural = None
        try:
            rep.enriched = enriched_shape(code, lang or "python")
        except Exception:
            rep.enriched = {}
        try:
            rep.efficiency = efficiency_summary(code)
            rep.complexity = rep.efficiency.get("complexity")
        except Exception:
            rep.efficiency = {}
        try:
            rep.value_flow = value_flow_shape(code)
            rep.flow_path = flow_path(code)
        except Exception:
            rep.value_flow = {}
        try:
            rep.algorithms = detect_algorithm(code, lang or "python")
        except Exception:
            rep.algorithms = []
        try:
            rep.patterns = detect_patterns(code, lang or "python")
        except Exception:
            rep.patterns = []
        try:
            rep.vulnerabilities = (
                find_precise_issues(code) + find_buffer_overflows(code) + detect_vulns_v2(code, lang or "python")
            )
        except Exception:
            rep.vulnerabilities = []
        try:
            rep.sinks = [s["category"] for s in detect_sinks(code)]
        except Exception:
            rep.sinks = []

    if project_dir is not None:
        from code_shape.core.composite_vector import composite_vector
        from code_shape.core.import_analysis import analyze_imports
        root = Path(project_dir)
        try:
            rep.composite = composite_vector(root)
        except Exception:
            rep.composite = {}
        try:
            rep.imports = analyze_imports(root)
        except Exception:
            rep.imports = {}
        # 3D neural-shape graph data (per-file dataflow + merged graph + contrib)
        try:
            from code_shape.reports.shape3d import build_shape3d_data
            rep.extra["shape3d"] = build_shape3d_data(str(root))
        except Exception:
            rep.extra["shape3d"] = None
        # derive counts from composite vector
        rep.file_count = int(rep.composite.get("FUNC", 0))  # placeholder; refined below
        rep.function_count = int(rep.composite.get("FUNC", 0))
        rep.connection_count = int(rep.composite.get("CONN", 0))

    return rep


def build_report(
    analysis_type: str,
    target: str,
    code: Optional[str] = None,
    lang: Optional[str] = None,
    project_dir: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> AnalysisReport:
    """Collect analysis and write report.md + report.html + data.json.

    Returns the populated AnalysisReport. The rendered files live under
    `reports/<date>/<analysis_type>/`.
    """
    rep = collect_analysis(analysis_type, target, code, lang, project_dir)
    if extra:
        rep.extra = extra

    # ── Shape memory: snapshot & cascading diff ────────────────────────────
    try:
        from code_shape.memory import snapshot_and_diff
        # Use project_dir root for store, fall back to cwd
        snap_root = Path(project_dir) if project_dir else Path.cwd()
        if code is not None and not project_dir:
            # Single-file target: use parent dir of target if it's a file path
            p = Path(target)
            if p.exists() and p.is_file():
                snap_root = p.parent
        rep.shape_diff = snapshot_and_diff(rep, snap_root)
    except Exception:
        rep.shape_diff = None

    from code_shape.reports.markdown import render_markdown
    from code_shape.reports.html import render_html
    from code_shape.art import render_mermaid_diagram

    out = rep.output_dir()
    out.mkdir(parents=True, exist_ok=True)

    (out / "report.md").write_text(render_markdown(rep), encoding="utf-8")
    (out / "report.html").write_text(render_html(rep), encoding="utf-8")
    (out / "report.mmd").write_text(render_mermaid_diagram(rep), encoding="utf-8")
    rep.save_json()

    return rep


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    rep = build_report("enriched", "sample: sum_list", code=sample, lang="python")
    print(f"Report written to: {rep.output_dir()}")
    print("  report.md  :", (rep.output_dir() / "report.md").exists())
    print("  report.html:", (rep.output_dir() / "report.html").exists())
    print("  data.json  :", (rep.output_dir() / "data.json").exists())
