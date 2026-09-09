#!/usr/bin/env python
"""code_shape/art.py — Artwork, ASCII mascots, and Mermaid diagrams for Morphē-chan.

Provides:
  - Cute ASCII art banners and characters for CLI and reports.
  - Mermaid (MMD) flowchart generator for code shape pipelines.
  - Base64 helpers for embedding mascot assets into HTML reports.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from code_shape.reports.builder import AnalysisReport

# Path to project assets directory
ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
LOGO_PATH = ASSETS_DIR / "morphe_chan_logo.png"
LOGO_THUMB_PATH = ASSETS_DIR / "morphe_chan_logo_thumb.png"
BADGE_PATH = ASSETS_DIR / "morphe_chan_badge.png"
BADGE_THUMB_PATH = ASSETS_DIR / "morphe_chan_badge_thumb.png"


ASCII_LOGO_TEXT = r"""
  __  __                  _       __          ___                 
 |  \/  | ___  _ __ _ __ | |__   ___ / /____ ____| |__   __ _ _ __   
 | |\/| |/ _ \| '__| '_ \| '_ \ / _ \ ____|____| '_ \ / _` | '_ \  
 | |  | | (_) | |  | |_) | | | |  __/          | | | | (_| | | | | 
 |_|  |_|\___/|_|  | .__/|_| |_|\___|          |_| |_|\__,_|_| |_| 
                   |_|   (モルフェ・ちゃん)   ~ Geometry has Truth! ~
""".strip("\n")


ASCII_MASCOT = r"""
             .---.                   /\
            / / \ \                 /  \
           |  |o|  |   (◕‿◕✿)      / /\ \
           \  \=/  /  /| ⬡ ⬢ |\   / /__\ \
            '---'    d| [✦] |b   \/______\/
                     (  | |  )
                   [Morphē-chan]
        "Code has shape. Geometry has truth!"
""".strip("\n")


ASCII_MASCOT_COMPACT = r"""
        (◕‿◕✿) [Morphē-chan] ✦ ⬡ 
  "Code has shape. Geometry has truth!"
""".strip("\n")


ASCII_CLI_BANNER = r"""
✦ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ✦
  __  __                  _       __          ___                 
 |  \/  | ___  _ __ _ __ | |__   ___ / /____ ____| |__   __ _ _ __   
 | |\/| |/ _ \| '__| '_ \| '_ \ / _ \ ____|____| '_ \ / _` | '_ \  
 | |  | | (_) | |  | |_) | | | |  __/          | | | | (_| | | | | 
 |_|  |_|\___/|_|  | .__/|_| |_|\___|          |_| |_|\__,_|_| |_| 
                   |_|   (モルフェ・ちゃん)   ~ Geometry has Truth! ~

             .---.                   /\
            / / \ \                 /  \
           |  |o|  |   (◕‿◕✿)      / /\ \
           \  \=/  /  /| ⬡ ⬢ |\   / /__\ \
            '---'    d| [✦] |b   \/______\/
                     (  | |  )
                   [Morphē-chan]
✦ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ✦
""".strip("\n")


def get_logo_base64(thumbnail: bool = True) -> str:
    """Return a base64 data URI for the Morphē-chan logo (thumb or full)."""
    p = LOGO_THUMB_PATH if (thumbnail and LOGO_THUMB_PATH.exists()) else LOGO_PATH
    if p.exists():
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{data}"
    return ""


def get_badge_base64(thumbnail: bool = True) -> str:
    """Return a base64 data URI for the Morphē-chan badge avatar."""
    p = BADGE_THUMB_PATH if (thumbnail and BADGE_THUMB_PATH.exists()) else BADGE_PATH
    if p.exists():
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{data}"
    return ""


def render_mermaid_diagram(rep: AnalysisReport) -> str:
    """Render a cute, styled Mermaid (MMD) flowchart for an AnalysisReport."""
    target_clean = rep.target.replace('"', "'").replace("\n", " ")
    if len(target_clean) > 40:
        target_clean = target_clean[:37] + "..."

    shape_summary = rep.shape or "N/A"
    if len(shape_summary) > 35:
        shape_summary = shape_summary[:32] + "..."

    complexity = rep.complexity or rep.efficiency.get("complexity", "O(1)")

    # Status verdict styling
    has_vulns = bool(rep.vulnerabilities)
    vuln_count = len(rep.vulnerabilities)
    if has_vulns:
        verdict_label = f"⚠️ Morphē-chan Warning: {vuln_count} Vuln(s) Detected! (⊙_⊙)"
        verdict_style = "fill:#450a0a,stroke:#ef4444,stroke-width:2px,color:#fecaca"
    else:
        verdict_label = "✦ Morphē-chan Verified: Clean Shape! (◕‿◕✿) ✦"
        verdict_style = "fill:#2e1065,stroke:#c084fc,stroke-width:2px,color:#f3e8ff"

    alg_count = len(rep.algorithms)
    pat_count = len(rep.patterns)
    dim_count = len(rep.enriched) if rep.enriched else len(rep.composite)

    mmd = f"""flowchart TD
    %% Morphē-chan (モルフェ・ちゃん) Code-Shape Pipeline MMD
    %% Generated: {rep.timestamp}

    subgraph Header["✧ Morphē-chan Geometric Analysis (モルフェ・ちゃん) ✧"]
        direction TB
        Input["📄 Target: {target_clean}<br/>[{rep.language or 'Code'}]"]
        Input --> Core["⬡ Morphē-chan Shape Engine (◕‿◕✿)<br/>[Vector Dimensionality: {dim_count} dims]"]
    end

    subgraph ShapeAnalysis["✧ Extracted Geometric Dimensions ✧"]
        direction LR
        Core --> S_Shape["🔷 Shape Signature<br/>{shape_summary}"]
        Core --> S_Eff["⚡ Efficiency & Complexity<br/>{complexity}"]
        Core --> S_Detect["🧩 Detectors<br/>{alg_count} Alg(s) • {pat_count} Pattern(s)"]
    end

    S_Shape --> Verdict["{verdict_label}"]
    S_Eff --> Verdict
    S_Detect --> Verdict

    classDef default fill:#171e2e,stroke:#2a3350,stroke-width:1px,color:#e6e9f0;
    classDef headerNode fill:#1e1b4b,stroke:#818cf8,stroke-width:2px,color:#e0e7ff;
    classDef coreNode fill:#3b0764,stroke:#d8b4fe,stroke-width:2px,color:#faf5ff;
    classDef branchNode fill:#1e293b,stroke:#38bdf8,stroke-width:1px,color:#f0f9ff;
    
    class Input headerNode;
    class Core coreNode;
    class S_Shape,S_Eff,S_Detect branchNode;
    style Verdict {verdict_style}
"""
    return mmd


def render_cascade_mermaid(diff: Any) -> str:
    """Render a Mermaid stateDiagram-v2 showing the shape state transition."""
    old_ts = (diff.old_timestamp or "prev")[:19]
    new_ts = (diff.new_timestamp or "now")[:19]
    score_pct = int(diff.cascade_score * 100)
    verdict_short = diff.cascade_verdict[:60].replace('"', "'")

    # Build dimension change notes
    top = diff.top_changed_dims(5)
    dim_lines = []
    for d in top:
        sign = "+" if d.delta > 0 else ""
        dim_lines.append(f"  {d.dim}: {sign}{d.delta:+.2f}")

    alg_note = ""
    if diff.algorithms_gained:
        alg_note += "  +alg: " + ", ".join(diff.algorithms_gained[:3])
    if diff.algorithms_lost:
        alg_note += "  -alg: " + ", ".join(diff.algorithms_lost[:3])

    pat_note = ""
    if diff.patterns_gained:
        pat_note += "  +pat: " + ", ".join(diff.patterns_gained[:3])
    if diff.patterns_lost:
        pat_note += "  -pat: " + ", ".join(diff.patterns_lost[:3])

    vuln_note = ""
    if diff.vulns_gained:
        vuln_note += "  +vuln: " + ", ".join(diff.vulns_gained[:3])
    if diff.vulns_fixed:
        vuln_note += "  -vuln(fixed): " + ", ".join(diff.vulns_fixed[:3])

    complexity_note = ""
    if diff.complexity_changed:
        complexity_note = f"  complexity: {diff.old_complexity} --> {diff.new_complexity}"

    dim_block = "\n".join(f"        note right of Cascade : {l}" for l in dim_lines) if dim_lines else ""

    mmd = f"""stateDiagram-v2
    %% Morphe-chan (morufe-chan) Shape Cascade Tracker
    %% Generated diff: {old_ts} -> {new_ts}

    [*] --> PrevShape : snapshot loaded

    PrevShape : Prev Shape State
    PrevShape : ({old_ts})
{complexity_note and f"    PrevShape : {complexity_note}" or ""}

    PrevShape --> Cascade : analyze + diff

    Cascade : Cascading Shape Change
    Cascade : cascade score = {score_pct}%
    Cascade : {verdict_short}
{chr(10).join(f"    Cascade : {l}" for l in dim_lines)}
{alg_note and f"    Cascade : {alg_note}" or ""}
{pat_note and f"    Cascade : {pat_note}" or ""}
{vuln_note and f"    Cascade : {vuln_note}" or ""}

    Cascade --> NewShape : shape recorded

    NewShape : New Shape State
    NewShape : ({new_ts})

    NewShape --> [*]
"""
    return mmd
