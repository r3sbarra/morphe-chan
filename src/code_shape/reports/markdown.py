#!/usr/bin/env python
"""reports/markdown.py — Render an AnalysisReport as Markdown."""

from __future__ import annotations

from typing import Any, Dict, List

from code_shape.art import ASCII_MASCOT, render_mermaid_diagram
from code_shape.reports.builder import AnalysisReport


def _grouped(vec: Dict[str, float], prefixes: List[str], top: int = 8) -> List[tuple]:
    """Group a prefixed vector (e.g. PRIM:*, EFF:*) and return top items."""
    groups: Dict[str, List[tuple]] = {}
    for k, v in vec.items():
        prefix = k.split(":")[0]
        groups.setdefault(prefix, []).append((k, v))
    out = []
    for p in prefixes:
        if p in groups:
            items = sorted(groups[p], key=lambda kv: -kv[1])[:top]
            out.append((p, items))
    return out


def _fmt(v: float) -> str:
    return f"{v:.3f}"


def render_markdown(rep: AnalysisReport) -> str:
    """Render the full Markdown report."""
    L: List[str] = []
    L.append(f"# Morphē-chan Analysis Report — {rep.analysis_type} (モルフェ・ちゃん)")
    L.append("")
    L.append('<p align="center">')
    L.append('  <img src="../../../assets/morphe_chan_badge.png" alt="Morphē-chan Badge" width="220" />')
    L.append('</p>')
    L.append("")
    L.append("```text")
    L.append(ASCII_MASCOT)
    L.append("```")
    L.append("")
    L.append(f"- **Target:** `{rep.target}`")
    L.append(f"- **Type:** {rep.analysis_type}")
    L.append(f"- **Date:** {rep.date}")
    L.append(f"- **Timestamp:** {rep.timestamp}")
    if rep.language:
        L.append(f"- **Language:** {rep.language}")
    L.append("")

    # ── Shape ─────────────────────────────────────────────────────────────
    if rep.shape or rep.structural:
        L.append("## Shape")
        L.append("")
        if rep.shape:
            L.append(f"- **Shape:** `{rep.shape}`")
        if rep.structural:
            L.append(f"- **Structural:** `{rep.structural}`")
        L.append("")

    # ── Enriched vector ───────────────────────────────────────────────────
    if rep.enriched:
        L.append("## Enriched Multi-Dimensional Shape")
        L.append("")
        L.append(f"Total dimensions: **{len(rep.enriched)}**")
        L.append("")
        for prefix, items in _grouped(rep.enriched, ["PRIM", "EFF", "FLOW", "LIB", "ALG", "PAT", "VULN", "PROP", "VAL"]):
            L.append(f"### {prefix}")
            L.append("")
            L.append("| Dimension | Value |")
            L.append("|---|---|")
            for k, v in items:
                L.append(f"| `{k}` | {_fmt(v)} |")
            L.append("")

    # ── Efficiency ────────────────────────────────────────────────────────
    if rep.efficiency:
        L.append("## Efficiency")
        L.append("")
        L.append(f"- **Complexity:** {rep.complexity or rep.efficiency.get('complexity', 'n/a')}")
        for k, v in rep.efficiency.items():
            if k == "complexity":
                continue
            L.append(f"- **{k.replace('_', ' ').title()}:** {v}")
        L.append("")

    # ── Value flow ────────────────────────────────────────────────────────
    if rep.flow_path or rep.value_flow:
        L.append("## Value Flow")
        L.append("")
        if rep.flow_path:
            L.append(f"- **Flow path:** `{rep.flow_path}`")
        if rep.value_flow:
            L.append("")
            L.append("| Dimension | Value |")
            L.append("|---|---|")
            for k, v in sorted(rep.value_flow.items(), key=lambda kv: -kv[1]):
                L.append(f"| `{k}` | {_fmt(v)} |")
        L.append("")

    # ── Algorithms ─────────────────────────────────────────────────────────
    if rep.algorithms:
        L.append("## Algorithms Detected")
        L.append("")
        L.append("| Algorithm | Score | Features hit |")
        L.append("|---|---|---|")
        for a in rep.algorithms:
            L.append(f"| {a.get('algorithm', '?')} | {a.get('score', 0):.2f} | {a.get('features_hit', 0)} |")
        L.append("")

    # ── Patterns ─────────────────────────────────────────────────────────
    if rep.patterns:
        L.append("## Patterns Detected")
        L.append("")
        L.append("| Pattern | Score | Features hit |")
        L.append("|---|---|---|")
        for p in rep.patterns:
            L.append(f"| {p.get('pattern', '?')} | {p.get('score', 0):.2f} | {p.get('features_hit', 0)} |")
        L.append("")

    # ── Vulnerabilities ───────────────────────────────────────────────────
    if rep.vulnerabilities:
        L.append("## Vulnerabilities / Security Findings")
        L.append("")
        L.append(f"**{len(rep.vulnerabilities)} finding(s)**")
        L.append("")
        L.append("| Type | Line | Sink | Source |")
        L.append("|---|---|---|---|")
        for v in rep.vulnerabilities:
            L.append(f"| {v.get('type', '?')} | {v.get('line', '?')} | `{v.get('sink', '?')}` | {v.get('source', '?')} |")
        L.append("")
    elif rep.analysis_type in ("vulns", "analyze", "enriched", "project"):
        L.append("## Vulnerabilities / Security Findings")
        L.append("")
        L.append("No vulnerabilities detected. ✅")
        L.append("")

    # ── Sinks ─────────────────────────────────────────────────────────────
    if rep.sinks:
        L.append("## Dangerous Sinks")
        L.append("")
        L.append(", ".join(f"`{s}`" for s in rep.sinks))
        L.append("")

    # ── Project composite ─────────────────────────────────────────────────
    if rep.composite:
        L.append("## Project Composite Vector")
        L.append("")
        L.append(f"Total dimensions: **{len(rep.composite)}**")
        L.append("")
        for prefix, items in _grouped(rep.composite, ["LANG", "PRIM", "FUNC", "CONN", "FLOW", "EFF", "SINK", "HARD", "IMP", "DEPTH"]):
            L.append(f"### {prefix}")
            L.append("")
            L.append("| Dimension | Value |")
            L.append("|---|---|")
            for k, v in items:
                L.append(f"| `{k}` | {_fmt(v)} |")
            L.append("")

    # ── Imports ───────────────────────────────────────────────────────────
    if rep.imports:
        L.append("## Imports / Dependencies")
        L.append("")
        L.append(f"- **Import count:** {rep.imports.get('import_count', 'n/a')}")
        L.append(f"- **Unique modules:** {rep.imports.get('unique_modules', 'n/a')}")
        L.append(f"- **Files with imports:** {rep.imports.get('files_with_imports', 'n/a')}")
        L.append("")

    # ── Extra sections ────────────────────────────────────────────────────
    for key, val in rep.extra.items():
        L.append(f"## {key.replace('_', ' ').title()}")
        L.append("")
        if isinstance(val, (dict, list)):
            L.append("```json")
            import json
            L.append(json.dumps(val, indent=2, default=str))
            L.append("```")
        else:
            L.append(str(val))
        L.append("")

    # ── Cascading Shape Changes ────────────────────────────────────────────
    diff = getattr(rep, "shape_diff", None)
    if diff is not None:
        L.append("## ⚡ Cascading Shape Changes")
        L.append("")
        L.append(f"> {diff.cascade_verdict}")
        L.append("")
        L.append(f"- **Cascade score:** `{diff.cascade_score:.3f}` (0=no change, 1=total shape shift)")
        L.append(f"- **Previous snapshot:** {diff.old_timestamp}")
        L.append(f"- **Current snapshot:** {diff.new_timestamp}")
        L.append("")

        if diff.complexity_changed:
            direction_icon = "🔴" if diff.complexity_direction == "degraded" else "🟢"
            L.append(f"### {direction_icon} Complexity Shift")
            L.append("")
            L.append(f"| Before | After | Direction |")
            L.append("|---|---|---|")
            L.append(f"| `{diff.old_complexity or 'n/a'}` | `{diff.new_complexity or 'n/a'}` | {diff.complexity_direction.upper()} |")
            L.append("")

        top = diff.top_changed_dims(10)
        if top:
            L.append("### 📐 Top Changed Dimensions")
            L.append("")
            L.append("| Dimension | Before | After | Delta |")
            L.append("|---|---|---|---|")
            for d in top:
                sign = "+" if d.delta > 0 else ""
                arrow = "▲" if d.delta > 0 else "▼"
                L.append(f"| `{d.dim}` | {d.old_val:.3f} | {d.new_val:.3f} | {arrow} {sign}{d.delta:+.3f} |")
            L.append("")

        for label, gained, lost in [
            ("Algorithms", diff.algorithms_gained, diff.algorithms_lost),
            ("Patterns",   diff.patterns_gained,   diff.patterns_lost),
            ("Vulnerabilities", diff.vulns_gained, diff.vulns_fixed),
        ]:
            if gained or lost:
                L.append(f"### {label}")
                L.append("")
                for g in gained:
                    L.append(f"- 🔵 **Gained:** `{g}`")
                for lo in lost:
                    action = "Fixed ✅" if label == "Vulnerabilities" else "Lost"
                    L.append(f"- 🔴 **{action}:** `{lo}`")
                L.append("")

        # Cascade state diagram
        from code_shape.art import render_cascade_mermaid
        L.append("### Cascade State Diagram")
        L.append("")
        L.append("```mermaid")
        L.append(render_cascade_mermaid(diff))
        L.append("```")
        L.append("")

    # ── Geometric Pipeline (MMD) ──────────────────────────────────────────
    L.append("## Morphē-chan Geometric Pipeline (MMD)")

    L.append("")
    L.append("```mermaid")
    L.append(render_mermaid_diagram(rep))
    L.append("```")
    L.append("")

    # ── Code snippet ──────────────────────────────────────────────────────
    if rep.code_snippet:
        L.append("## Analyzed Code")
        L.append("")
        L.append("```python")
        L.append(rep.code_snippet)
        L.append("```")
        L.append("")

    L.append("---")
    L.append(f"*Generated with 💜 by Morphē-chan (モルフェ・ちゃん) on {rep.timestamp}. Code has shape. Geometry has truth!*")
    L.append("")
    return "\n".join(L)
