#!/usr/bin/env python
"""reports/html.py — Render an AnalysisReport as an interactive HTML report.

Produces a self-contained HTML page with Chart.js interactive graphs (bar,
doughnut, radar, line) plus a rich narrative of the research findings. Chart.js
is vendored locally (static/vendor/chart.umd.min.js) so the report works fully
offline.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from code_shape.art import get_badge_base64, ASCII_MASCOT, render_mermaid_diagram
from code_shape.reports.builder import AnalysisReport

# Path to vendored Chart.js, resolved relative to this file.
_CHART_JS = Path(__file__).resolve().parents[3] / "static" / "vendor" / "chart.umd.min.js"


def _grouped(vec: Dict[str, float], prefixes: List[str], top: int = 10) -> List[tuple]:
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


def _chart_js_inline() -> str:
    """Return the vendored Chart.js source (or a CDN fallback if missing)."""
    if _CHART_JS.exists():
        return _CHART_JS.read_text(encoding="utf-8")
    return '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>'


def _bar_chart(canvas_id: str, labels: List[str], values: List[float], title: str, color: str = "#4f8cff") -> str:
    return f"""
    <div class="chart-card">
      <h3>{title}</h3>
      <div class="chart-wrap"><canvas id="{canvas_id}"></canvas></div>
    </div>
    <script>
    new Chart(document.getElementById('{canvas_id}'), {{
      type: 'bar',
      data: {{
        labels: {json.dumps(labels)},
        datasets: [{{ label: '{title}', data: {json.dumps(values)}, backgroundColor: '{color}', borderRadius: 4 }}]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ beginAtZero: true }} }}
      }}
    }});
    </script>"""


def _doughnut_chart(canvas_id: str, labels: List[str], values: List[float], title: str) -> str:
    return f"""
    <div class="chart-card">
      <h3>{title}</h3>
      <div class="chart-wrap"><canvas id="{canvas_id}"></canvas></div>
    </div>
    <script>
    new Chart(document.getElementById('{canvas_id}'), {{
      type: 'doughnut',
      data: {{
        labels: {json.dumps(labels)},
        datasets: [{{ data: {json.dumps(values)}, borderWidth: 1 }}]
      }},
      options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'right' }} }} }}
    }});
    </script>"""


def _radar_chart(canvas_id: str, labels: List[str], values: List[float], title: str) -> str:
    return f"""
    <div class="chart-card">
      <h3>{title}</h3>
      <div class="chart-wrap"><canvas id="{canvas_id}"></canvas></div>
    </div>
    <script>
    new Chart(document.getElementById('{canvas_id}'), {{
      type: 'radar',
      data: {{
        labels: {json.dumps(labels)},
        datasets: [{{ label: '{title}', data: {json.dumps(values)}, borderColor: '#4f8cff', backgroundColor: 'rgba(79,140,255,0.2)', pointRadius: 3 }}]
      }},
      options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
    }});
    </script>"""


def _line_chart(canvas_id: str, labels: List[str], values: List[float], title: str) -> str:
    return f"""
    <div class="chart-card">
      <h3>{title}</h3>
      <div class="chart-wrap"><canvas id="{canvas_id}"></canvas></div>
    </div>
    <script>
    new Chart(document.getElementById('{canvas_id}'), {{
      type: 'line',
      data: {{
        labels: {json.dumps(labels)},
        datasets: [{{ label: '{title}', data: {json.dumps(values)}, borderColor: '#4f8cff', backgroundColor: 'rgba(79,140,255,0.1)', fill: true, tension: 0.3 }}]
      }},
      options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
    }});
    </script>"""


def _table(headers: List[str], rows: List[List[str]]) -> str:
    thead = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>'


def render_html(rep: AnalysisReport) -> str:
    """Render the full interactive HTML report."""
    parts: List[str] = []

    badge_b64 = get_badge_base64(thumbnail=True)
    if rep.vulnerabilities:
        speech = f"⚠️ Watch out, senpai! Morphē-chan detected {len(rep.vulnerabilities)} security finding(s)! Review dangerous sinks carefully! (⊙_⊙)"
    elif rep.algorithms or rep.patterns:
        speech = f"✨ Geometric symmetry aligned! Found {len(rep.algorithms)} algorithm(s) and {len(rep.patterns)} pattern(s)! Looking sharp, senpai! (◕‿◕✿) ✦"
    else:
        speech = "✨ Code shape analyzed smoothly! Geometry has truth, senpai! (◕‿◕✿) ✦"

    # ── Header ───────────────────────────────────────────────────────────
    parts.append(f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Morphē-chan Report — {rep.analysis_type}</title>
<style>
  :root {{ --bg:#0f1420; --card:#171e2e; --text:#e6e9f0; --muted:#9aa3b5; --accent:#a855f7; --accent-blue:#4f8cff; --good:#3ddc84; --warn:#ffb454; --bad:#ff5c5c; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); line-height:1.55; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px 60px; }}
  header.hero-header {{ display:flex; align-items:center; gap:24px; border-bottom:1px solid #2a3350; padding-bottom:24px; margin-bottom:28px; flex-wrap:wrap; }}
  .avatar-box {{ position:relative; flex-shrink:0; }}
  .avatar-img {{ width:100px; height:100px; border-radius:50%; border:3px solid #a855f7; box-shadow:0 0 24px rgba(168,85,247,.45); object-fit:cover; background:#171e2e; display:block; transition:transform .3s ease; }}
  .avatar-img:hover {{ transform:scale(1.08) rotate(3deg); }}
  .header-main {{ flex:1; min-width:280px; }}
  .title-row {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:4px; }}
  h1 {{ margin:0; font-size:26px; }}
  .jp-tag {{ color:#c084fc; font-size:16px; font-weight:normal; }}
  .type-badge {{ background:linear-gradient(135deg, #7c3aed, #a855f7); color:#fff; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; }}
  .sub {{ color:var(--muted); font-size:14px; margin-bottom:10px; }}
  .speech-bubble {{ background:linear-gradient(135deg, rgba(168,85,247,.12), rgba(79,140,255,.08)); border:1px solid rgba(168,85,247,.35); border-radius:12px; padding:8px 14px; margin-bottom:12px; font-size:13.5px; color:#f3e8ff; display:inline-flex; align-items:center; gap:8px; }}
  .bubble-sparkle {{ color:#f472b6; font-size:14px; }}
  .meta {{ display:flex; flex-wrap:wrap; gap:10px; }}
  .chip {{ background:var(--card); border:1px solid #2a3350; border-radius:20px; padding:4px 12px; font-size:12px; color:var(--muted); }}
  .chip b {{ color:var(--text); }}
  h2 {{ font-size:19px; margin:34px 0 12px; color:var(--accent); }}
  h3 {{ font-size:15px; margin:0 0 10px; color:var(--text); }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }}
  .art-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(360px,1fr)); gap:16px; margin:14px 0; }}
  .art-card {{ background:var(--card); border:1px solid #2a3350; border-radius:10px; padding:16px; }}
  .card-title {{ font-size:13px; font-weight:600; color:#c084fc; margin-bottom:10px; text-transform:uppercase; letter-spacing:.5px; }}
  .mermaid-box {{ background:#0a0e18; border:1px solid #232c44; border-radius:8px; padding:14px; overflow-x:auto; }}
  .mermaid-box pre {{ margin:0; background:transparent; border:none; padding:0; font-family:'SF Mono',Consolas,Menlo,monospace; font-size:12px; color:#e6e9f0; }}
  .ascii-box {{ background:#0a0e18; border:1px solid #232c44; border-radius:8px; padding:14px; overflow-x:auto; margin:0; }}
  .ascii-box code {{ font-family:'SF Mono',Consolas,Menlo,monospace; font-size:11.5px; color:#c084fc; line-height:1.35; white-space:pre; display:block; }}
  .chart-card {{ background:var(--card); border:1px solid #2a3350; border-radius:10px; padding:16px; }}
  .chart-wrap {{ position:relative; height:280px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid #2a3350; border-radius:8px; overflow:hidden; font-size:13px; }}
  th {{ text-align:left; background:#1c2436; padding:8px 12px; color:var(--muted); font-weight:600; }}
  td {{ padding:7px 12px; border-top:1px solid #232c44; }}
  .stat-row {{ display:flex; flex-wrap:wrap; gap:14px; margin:14px 0; }}
  .stat {{ flex:1; min-width:150px; background:var(--card); border:1px solid #2a3350; border-radius:10px; padding:14px 16px; }}
  .stat .num {{ font-size:26px; font-weight:700; color:var(--accent); }}
  .stat .lbl {{ font-size:12px; color:var(--muted); }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }}
  .b-good {{ background:rgba(61,220,132,.15); color:var(--good); }}
  .b-warn {{ background:rgba(255,180,84,.15); color:var(--warn); }}
  .b-bad {{ background:rgba(255,92,92,.15); color:var(--bad); }}
  pre {{ background:#0a0e18; border:1px solid #2a3350; border-radius:8px; padding:14px; overflow:auto; font-size:12.5px; }}
  code {{ font-family:'SF Mono',Consolas,Menlo,monospace; }}
  .note {{ color:var(--muted); font-size:13px; }}
  footer {{ margin-top:40px; color:var(--muted); font-size:13px; text-align:center; padding-top:20px; border-top:1px solid #2a3350; }}
  .footer-mascot {{ display:inline-flex; align-items:center; gap:8px; justify-content:center; }}
</style>
</head>
<body>
<div class="wrap">
<header class="hero-header">
  <div class="avatar-box">
    <img src="{badge_b64}" class="avatar-img" alt="Morphē-chan Mascot Avatar" />
  </div>
  <div class="header-main">
    <div class="title-row">
      <h1>Morphē-chan Analysis Report</h1>
      <span class="jp-tag">(モルフェ・ちゃん)</span>
      <span class="type-badge">{rep.analysis_type}</span>
    </div>
    <div class="sub">Multi-Dimensional Geometric Code Analysis & Synthesis</div>
    <div class="speech-bubble">
      <span class="bubble-sparkle">✦</span>
      <span>{speech}</span>
    </div>
    <div class="meta">
      <span class="chip">Type: <b>{rep.analysis_type}</b></span>
      <span class="chip">Target: <b>{rep.target}</b></span>
      <span class="chip">Date: <b>{rep.date}</b></span>
      <span class="chip">Time: <b>{rep.timestamp}</b></span>
      {f'<span class="chip">Language: <b>{rep.language}</b></span>' if rep.language else ''}
    </div>
  </div>
</header>
""")

    # ── Stat row ──────────────────────────────────────────────────────────
    stats = []
    if rep.enriched:
        stats.append(("Enriched dims", str(len(rep.enriched))))
    if rep.composite:
        stats.append(("Composite dims", str(len(rep.composite))))
    if rep.algorithms:
        stats.append(("Algorithms", str(len(rep.algorithms))))
    if rep.patterns:
        stats.append(("Patterns", str(len(rep.patterns))))
    if rep.vulnerabilities:
        stats.append(("Vulns", str(len(rep.vulnerabilities))))
    if rep.function_count:
        stats.append(("Functions", str(rep.function_count)))
    if rep.connection_count:
        stats.append(("Connections", str(rep.connection_count)))
    if stats:
        parts.append('<div class="stat-row">' + "".join(
            f'<div class="stat"><div class="num">{v}</div><div class="lbl">{k}</div></div>' for k, v in stats
        ) + '</div>')

    # ── MMD Pipeline & Mascot Art ─────────────────────────────────────────
    parts.append(f"""
<h2>Morphē-chan Geometric Pipeline (MMD) & Mascots</h2>
<div class="art-grid">
  <div class="art-card">
    <div class="card-title">✦ Mermaid Flowchart (MMD) ✦</div>
    <div class="mermaid-box">
      <pre class="mermaid">{render_mermaid_diagram(rep)}</pre>
    </div>
  </div>
  <div class="art-card">
    <div class="card-title">✦ Morphē-chan Mascot Art ✦</div>
    <div class="ascii-box">
      <code>{ASCII_MASCOT}</code>
    </div>
  </div>
</div>
""")

    # ── Shape ─────────────────────────────────────────────────────────────
    if rep.shape or rep.structural:
        parts.append("<h2>Shape</h2>")
        if rep.shape:
            parts.append(f'<p><b>Shape:</b> <code>{rep.shape}</code></p>')
        if rep.structural:
            parts.append(f'<p><b>Structural:</b> <code>{rep.structural}</code></p>')

    # ── Enriched vector charts ───────────────────────────────────────────
    if rep.enriched:
        parts.append("<h2>Enriched Multi-Dimensional Shape</h2>")
        parts.append(f'<p class="note">Total dimensions: <b>{len(rep.enriched)}</b>. '
                     'Hover bars for exact values; charts are interactive.</p>')
        parts.append('<div class="grid">')
        for prefix, items in _grouped(rep.enriched, ["PRIM", "EFF", "FLOW", "LIB", "ALG", "PAT", "VULN", "PROP", "VAL"]):
            labels = [k for k, _ in items]
            values = [v for _, v in items]
            cid = f"enr_{prefix.lower()}"
            if prefix in ("PRIM", "EFF", "FLOW"):
                parts.append(_bar_chart(cid, labels, values, f"{prefix} dimensions"))
            elif prefix in ("LIB", "ALG", "PAT", "VULN"):
                parts.append(_doughnut_chart(cid, labels, values, f"{prefix} distribution"))
            else:
                parts.append(_bar_chart(cid, labels, values, f"{prefix} dimensions"))
        parts.append("</div>")

    # ── Efficiency ───────────────────────────────────────────────────────
    if rep.efficiency:
        parts.append("<h2>Efficiency</h2>")
        parts.append(f'<p><b>Complexity:</b> <code>{rep.complexity or rep.efficiency.get("complexity", "n/a")}</code></p>')
        eff_items = [(k.replace("_", " ").title(), v) for k, v in rep.efficiency.items() if k != "complexity"]
        if eff_items:
            parts.append(_bar_chart("eff_chart", [k for k, _ in eff_items], [float(v) for _, v in eff_items], "Efficiency signals"))

    # ── Value flow ───────────────────────────────────────────────────────
    if rep.flow_path or rep.value_flow:
        parts.append("<h2>Value Flow</h2>")
        if rep.flow_path:
            parts.append(f'<p><b>Flow path:</b> <code>{rep.flow_path}</code></p>')
        if rep.value_flow:
            vf_items = sorted(rep.value_flow.items(), key=lambda kv: -kv[1])[:12]
            parts.append(_bar_chart("vf_chart", [k for k, _ in vf_items], [v for _, v in vf_items], "Value-flow dimensions"))

    # ── Algorithms ────────────────────────────────────────────────────────
    if rep.algorithms:
        parts.append("<h2>Algorithms Detected</h2>")
        parts.append(_table(
            ["Algorithm", "Score", "Features hit"],
            [[a.get("algorithm", "?"), f'{a.get("score", 0):.2f}', str(a.get("features_hit", 0))] for a in rep.algorithms],
        ))

    # ── Patterns ─────────────────────────────────────────────────────────
    if rep.patterns:
        parts.append("<h2>Patterns Detected</h2>")
        parts.append(_table(
            ["Pattern", "Score", "Features hit"],
            [[p.get("pattern", "?"), f'{p.get("score", 0):.2f}', str(p.get("features_hit", 0))] for p in rep.patterns],
        ))

    # ── Vulnerabilities ───────────────────────────────────────────────────
    if rep.vulnerabilities:
        parts.append("<h2>Vulnerabilities / Security Findings</h2>")
        parts.append(f'<p><span class="badge b-bad">{len(rep.vulnerabilities)} finding(s)</span></p>')
        parts.append(_table(
            ["Type", "Line", "Sink", "Source"],
            [[v.get("type", "?"), str(v.get("line", "?")), f'<code>{v.get("sink", "?")}</code>', str(v.get("source", "?"))] for v in rep.vulnerabilities],
        ))
        # vuln type distribution doughnut
        from collections import Counter
        vc = Counter(v.get("type", "?") for v in rep.vulnerabilities)
        parts.append('<div class="grid">')
        parts.append(_doughnut_chart("vuln_chart", list(vc.keys()), list(vc.values()), "Vulnerability types"))
        parts.append("</div>")
    elif rep.analysis_type in ("vulns", "analyze", "enriched", "project"):
        parts.append('<h2>Vulnerabilities / Security Findings</h2><p><span class="badge b-good">No vulnerabilities detected</span></p>')

    # ── Sinks ────────────────────────────────────────────────────────────
    if rep.sinks:
        parts.append("<h2>Dangerous Sinks</h2>")
        parts.append("<p>" + " ".join(f'<span class="badge b-warn">{s}</span>' for s in rep.sinks) + "</p>")

    # ── Project composite ─────────────────────────────────────────────────
    if rep.composite:
        parts.append("<h2>Project Composite Vector</h2>")
        parts.append(f'<p class="note">Total dimensions: <b>{len(rep.composite)}</b> — the full geometric fingerprint of the project.</p>')
        parts.append('<div class="grid">')
        for prefix, items in _grouped(rep.composite, ["LANG", "PRIM", "FUNC", "CONN", "FLOW", "EFF", "SINK", "HARD", "IMP", "DEPTH"]):
            labels = [k for k, _ in items]
            values = [v for _, v in items]
            cid = f"comp_{prefix.lower()}"
            if prefix == "LANG":
                parts.append(_doughnut_chart(cid, labels, values, "Language distribution"))
            elif prefix in ("PRIM", "FLOW", "EFF"):
                parts.append(_bar_chart(cid, labels, values, f"{prefix} dimensions"))
            else:
                parts.append(_bar_chart(cid, labels, values, f"{prefix} dimensions"))
        parts.append("</div>")

    # ── Imports ───────────────────────────────────────────────────────────
    if rep.imports:
        parts.append("<h2>Imports / Dependencies</h2>")
        parts.append('<div class="stat-row">')
        for k in ("import_count", "unique_modules", "files_with_imports"):
            if k in rep.imports:
                parts.append(f'<div class="stat"><div class="num">{rep.imports[k]}</div><div class="lbl">{k.replace("_", " ").title()}</div></div>')
        parts.append("</div>")

    # ── Extra sections ────────────────────────────────────────────────────
    for key, val in rep.extra.items():
        parts.append(f"<h2>{key.replace('_', ' ').title()}</h2>")
        if isinstance(val, (dict, list)):
            parts.append(f"<pre>{json.dumps(val, indent=2, default=str)}</pre>")
        else:
            parts.append(f"<p>{val}</p>")

    # ── Code snippet ─────────────────────────────────────────────────────
    if rep.code_snippet:
        parts.append("<h2>Analyzed Code</h2>")
        parts.append(f"<pre><code>{rep.code_snippet}</code></pre>")

    # ── Cascading Shape Changes ───────────────────────────────────────────
    diff = getattr(rep, "shape_diff", None)
    if diff is not None:
        direction_color = {"degraded": "var(--bad)", "improved": "var(--good)", "same": "var(--muted)"}.get(
            diff.complexity_direction, "var(--muted)"
        )
        score_pct = int(diff.cascade_score * 100)
        verdict_esc = diff.cascade_verdict.replace("<", "&lt;").replace(">", "&gt;")

        # Build pill badges for categoricals
        gained_pills = "".join(
            f'<span class="badge b-good">+{g}</span> '
            for lst, _color in [
                (diff.algorithms_gained, "good"),
                (diff.patterns_gained, "good"),
                (diff.vulns_fixed, "good"),
            ] for g in lst
        )
        lost_pills = "".join(
            f'<span class="badge b-bad">−{lo}</span> '
            for lst in [diff.algorithms_lost, diff.patterns_lost]
            for lo in lst
        )
        vuln_gained_pills = "".join(
            f'<span class="badge b-bad">+{v}</span> '
            for v in diff.vulns_gained
        )

        # Build the ± bar chart data
        top = diff.top_changed_dims(12)
        cascade_labels = [d.dim for d in top]
        cascade_deltas = [round(d.delta, 4) for d in top]
        cascade_colors = ["rgba(61,220,132,.75)" if v >= 0 else "rgba(255,92,92,.75)" for v in cascade_deltas]

        # Mermaid cascade diagram
        from code_shape.art import render_cascade_mermaid
        cascade_mmd = render_cascade_mermaid(diff).replace("`", "&#96;")

        complexity_html = ""
        if diff.complexity_changed:
            complexity_html = f"""
            <div style="margin:10px 0; padding:10px 14px; background:#0a0e18; border:1px solid {direction_color};
                        border-radius:8px; font-size:13px; color:{direction_color};">
              ⚡ <b>Complexity shifted:</b>
              <code>{diff.old_complexity or "n/a"}</code>
              &rarr; <code>{diff.new_complexity or "n/a"}</code>
              &nbsp;<span class="badge {'b-bad' if diff.complexity_direction == 'degraded' else 'b-good'}">{diff.complexity_direction.upper()}</span>
            </div>"""

        parts.append(f"""
<h2>⚡ Cascading Shape Changes</h2>
<div style="border:1px solid rgba(168,85,247,.35); border-radius:12px; padding:20px; background:linear-gradient(135deg,rgba(168,85,247,.06),rgba(79,140,255,.04)); margin:16px 0;">
  <div class="speech-bubble" style="margin-bottom:14px;">
    <span class="bubble-sparkle">⬡</span>
    <span>{verdict_esc}</span>
  </div>
  <div class="stat-row">
    <div class="stat">
      <div class="num" style="color:{'var(--bad)' if diff.cascade_score > 0.5 else 'var(--warn)' if diff.cascade_score > 0.2 else 'var(--good)'};">{score_pct}%</div>
      <div class="lbl">Cascade Score</div>
    </div>
    <div class="stat">
      <div class="num">{len(diff.vector_delta)}</div>
      <div class="lbl">Dims Changed</div>
    </div>
    <div class="stat">
      <div class="num" style="color:var(--good);">{len(diff.algorithms_gained)+len(diff.patterns_gained)+len(diff.vulns_fixed)}</div>
      <div class="lbl">Gains</div>
    </div>
    <div class="stat">
      <div class="num" style="color:var(--bad);">{len(diff.algorithms_lost)+len(diff.patterns_lost)+len(diff.vulns_gained)}</div>
      <div class="lbl">Losses</div>
    </div>
  </div>
  {complexity_html}
  <p style="font-size:12px; color:var(--muted); margin:8px 0 0;">
    Prev: <code>{diff.old_timestamp}</code> &rarr; Now: <code>{diff.new_timestamp}</code>
  </p>
</div>
""")

        if cascade_labels:
            parts.append('<div class="grid">')
            parts.append(f"""
    <div class="chart-card">
      <h3>Top Dimension Deltas</h3>
      <div class="chart-wrap"><canvas id="cascade_delta_chart"></canvas></div>
    </div>
    <script>
    new Chart(document.getElementById('cascade_delta_chart'), {{
      type: 'bar',
      data: {{
        labels: {json.dumps(cascade_labels)},
        datasets: [{{
          label: 'Delta',
          data: {json.dumps(cascade_deltas)},
          backgroundColor: {json.dumps(cascade_colors)},
          borderRadius: 4
        }}]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }}, title: {{ display: false }} }},
        scales: {{ y: {{ beginAtZero: false }} }}
      }}
    }});
    </script>
""")
            parts.append("</div>")

        if gained_pills or lost_pills or vuln_gained_pills:
            parts.append("<div style='margin:10px 0 20px; line-height:2;'>")
            if gained_pills:
                parts.append(f"<p><b>Gained:</b> {gained_pills}</p>")
            if lost_pills:
                parts.append(f"<p><b>Lost:</b> {lost_pills}</p>")
            if vuln_gained_pills:
                parts.append(f"<p><b>New Vulns ⚠️:</b> {vuln_gained_pills}</p>")
            parts.append("</div>")

        # Cascade MMD
        parts.append(f"""
<div class="art-grid">
  <div class="art-card">
    <div class="card-title">⬡ Shape Cascade State Diagram</div>
    <div class="mermaid-box">
      <pre class="mermaid">{cascade_mmd}</pre>
    </div>
  </div>
</div>
""")


    # ── Footer + Chart.js + Mermaid.js ────────────────────────────────────
    parts.append(f"""
<footer>
  <div class="footer-mascot">
    <img src="{badge_b64}" width="28" height="28" style="border-radius:50%; vertical-align:middle;" />
    <span>Generated with 💜 by <b>Morphē-chan (モルフェ・ちゃん)</b> on {rep.timestamp} · <i>Code has shape. Geometry has truth! ✦</i></span>
  </div>
</footer>
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>if (window.mermaid) {{ mermaid.initialize({{ startOnLoad: true, theme: 'dark' }}); }}</script>
<script>{_chart_js_inline()}</script>
</body>
</html>
""")

    return "\n".join(parts)
