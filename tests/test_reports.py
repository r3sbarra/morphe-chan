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


def test_shape3d_data_builds_payload(tmp_path):
    """Project scan produces the 3D-graph payload (files, merged graph, contrib)."""
    from code_shape.reports.shape3d import build_shape3d_data
    # a tiny project with two python files that call each other
    (tmp_path / "a.py").write_text("def helper(x):\n    return x + 1\n")
    (tmp_path / "b.py").write_text("from a import helper\ndef main():\n    return helper(2)\n")
    data = build_shape3d_data(str(tmp_path))
    assert data["file_count"] == 2
    assert data["files"][0]["path"] == "__project__"
    assert data["merged_graph"] is not None
    assert "helper" in data["merged_graph"]["functions"]
    assert data["contrib"]  # non-empty
    assert data["composite"]


def test_shape3d_html_embeds_renderer():
    """shape3d_html emits the stage + Three.js renderer + DATA payload."""
    from code_shape.reports.shape3d import build_shape3d_data, shape3d_html, SHAPE3D_JS
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        pathlib.Path(d, "x.py").write_text("def f():\n    return 1\n")
        data = build_shape3d_data(d)
    html = shape3d_html(data)
    assert "shape-stage" in html
    assert 'id="shape3d"' in html
    assert "const DATA = {" in html
    assert "initShape3D" in html
    assert "THREE.WebGLRenderer" in SHAPE3D_JS


def test_project_report_includes_3d_graph(tmp_path, monkeypatch):
    """A project report embeds the 3D neural-shape graph section."""
    import code_shape.reports.builder as builder
    monkeypatch.setattr(builder, "REPORT_ROOT", tmp_path)
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "m.py").write_text("def f():\n    return 1\n")
    rep = build_report("project", "proj", project_dir=str(tmp_path / "proj"))
    html = render_html(rep)
    assert "3D Neural Shape" in html
    assert 'id="shape3d"' in html
    assert "THREE.WebGLRenderer" in html  # Three.js vendored inline
