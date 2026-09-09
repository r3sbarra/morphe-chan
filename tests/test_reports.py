"""Tests for the Morphē-chan reports module.

Verifies that analysis reports generate the dated/typed folder with
report.md, report.html (interactive Chart.js), and data.json.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.reports import build_report, collect_analysis, render_markdown, render_html


SAMPLE = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"


def test_collect_analysis_enriched():
    rep = collect_analysis("enriched", "sample", code=SAMPLE, lang="python")
    assert rep.analysis_type == "enriched"
    assert rep.shape is not None
    assert "RETURN" in rep.shape
    assert rep.enriched  # non-empty
    assert rep.efficiency.get("complexity") == "O(n)"
    assert rep.date  # YYYY-MM-DD


def test_collect_analysis_vulns():
    vuln = "import hashlib\nh = hashlib.md5(b'x').hexdigest()\nimport os\nos.system('ls')"
    rep = collect_analysis("vulns", "sample", code=vuln, lang="python")
    types = {v.get("type") for v in rep.vulnerabilities}
    assert "WEAK_HASH" in types or "CMD_INJECTION" in types


def test_render_markdown_has_sections():
    rep = collect_analysis("enriched", "sample", code=SAMPLE, lang="python")
    md = render_markdown(rep)
    assert "# Morphē-chan Analysis Report" in md
    assert "## Shape" in md
    assert "## Enriched Multi-Dimensional Shape" in md
    assert "## Efficiency" in md


def test_render_html_interactive():
    rep = collect_analysis("enriched", "sample", code=SAMPLE, lang="python")
    html = render_html(rep)
    assert "<!DOCTYPE html>" in html
    assert "<canvas" in html          # interactive charts
    assert "new Chart(" in html       # Chart.js instantiation
    assert "Chart" in html and "</script>" in html  # Chart.js embedded (vendored inline)


def test_build_report_writes_files(tmp_path, monkeypatch):
    # Redirect the reports root to a temp dir so we don't pollute the repo.
    import code_shape.reports.builder as builder
    monkeypatch.setattr(builder, "REPORT_ROOT", tmp_path)

    rep = build_report("enriched", "sample", code=SAMPLE, lang="python")
    out = rep.output_dir()
    assert (out / "report.md").exists()
    assert (out / "report.html").exists()
    assert (out / "report.mmd").exists()
    assert (out / "data.json").exists()
    # dated + typed folder layout
    assert out.parent.name == rep.date
    assert out.name == "enriched"


def test_reports_include_art_and_mmd():
    rep = collect_analysis("enriched", "sample", code=SAMPLE, lang="python")
    md = render_markdown(rep)
    assert "Morphē-chan" in md
    assert "```mermaid" in md
    assert "```text" in md

    html = render_html(rep)
    assert "morphe-avatar" in html or "avatar-img" in html
    assert "data:image/png;base64," in html
    assert "mermaid" in html
    assert "Morphē-chan" in html
