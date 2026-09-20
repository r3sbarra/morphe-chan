"""Tests for vulnerability-finding USAGE: remediation + project posture scanner.

These make the findings actionable:
- every finding carries concrete `remediation` guidance (taxonomy.REMEDIATION_GUIDE)
- posture.analyze() aggregates findings into a risk score/grade + per-file ranking
- posture.remediations() groups fix actions per file/type
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.security.taxonomy import enrich_vulnerability, REMEDIATION_GUIDE
from code_shape.security import posture
from code_shape.security.posture import analyze, remediations, severity_counts


def _finding(vtype, severity="HIGH", file="app.py", line=1):
    return {
        "type": vtype, "line": line, "sink": "x", "source": None,
        "shape_dimension": "FLOW:X", "code_line": "", "file": file,
        "function": "f", "function_lines": [line, line], "shape_part": "",
        "path": "", "path_hops": [], "severity": severity,
    }


def test_remediation_field_present():
    r = enrich_vulnerability(_finding("SQL_INJECTION"), None)
    assert "remediation" in r
    assert "parameterized" in r["remediation"]  # SQLi -> parameterize guidance


def test_remediation_guide_covers_all_taxonomy_types():
    from code_shape.security.taxonomy import VULN_TAXONOMY
    missing = [t for t in VULN_TAXONOMY if t not in REMEDIATION_GUIDE]
    # every real vuln type should have concrete guidance
    assert not missing, missing


def test_analyze_aggregates_and_grades():
    issues = [
        _finding("SQL_INJECTION", "CRITICAL"),
        _finding("XSS", "HIGH"),
        _finding("WEAK_HASH", "MEDIUM", file="util.py", line=5),
    ]
    prof = analyze(issues)
    assert prof["total_findings"] == 3
    assert prof["by_severity"]["CRITICAL"] == 1
    assert prof["by_severity"]["HIGH"] == 1
    assert prof["by_severity"]["MEDIUM"] == 1
    assert prof["risk_score"] >= 1.0  # worst (CRITICAL) drives risk
    assert prof["grade"] == "F"


def test_analyze_ranks_riskiest_file_first():
    issues = [
        _finding("SQL_INJECTION", "CRITICAL", file="a.py"),
        _finding("XSS", "MEDIUM", file="b.py"),
        _finding("WEAK_HASH", "MEDIUM", file="b.py"),
    ]
    prof = analyze(issues)
    assert prof["top_files"][0]["file"].endswith("a.py")  # CRITICAL file first


def test_severity_counts():
    issues = [_finding("SQL_INJECTION", "CRITICAL"), _finding("XSS", "HIGH")]
    c = severity_counts(issues)
    assert c == {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 0, "LOW": 0}


def test_remediations_group_by_file():
    issues = [_finding("SQL_INJECTION", "CRITICAL", file="a.py"),
              _finding("XSS", "MEDIUM", file="a.py", line=9)]
    acts = remediations(issues, by_file=True)
    assert "a.py" in acts and len(acts["a.py"]) == 2
    assert any("L9 XSS" in a for a in acts["a.py"])


def test_scan_dir_finds_vulns(tmp_path):
    (tmp_path / "app.py").write_text(
        "def f(req):\n    name = req.form['name']\n"
        "    return db.execute('SELECT * FROM t WHERE n=' + name)")
    (tmp_path / "ok.js").write_text("function f(x) { return x; }")
    issues = posture.scan_dir(str(tmp_path))
    sql = [i for i in issues if i["type"] == "SQL_INJECTION"]
    assert sql, issues
    assert all(i["file"].endswith("app.py") for i in sql)


def test_report_builder_counts_precise_vulns():
    # The reports builder must count vulnerabilities via precise_issues only
    # (detect_vulns_v2 was dead weight returning empty and a latent double-
    # count risk). A SQLi snippet yields exactly one finding in the report.
    from code_shape.reports.builder import build_report
    code = "def f(req):\n    name = req.form['name']\n    return db.execute('SELECT * FROM t WHERE n = ' + name)"
    r = build_report("vulns", "t.py", code=code, lang="python")
    types = [v["type"] for v in r.vulnerabilities]
    assert types.count("SQL_INJECTION") == 1, types


def test_scan_project_captures_cross_file_taint(tmp_path):
    # Source in views.py reaches a sink in db.py across module boundary.
    (tmp_path / "views.py").write_text(
        "from db import query\n"
        "def login(request):\n"
        "    name = request.form['name']\n"
        "    return query.get_user(name)\n")
    (tmp_path / "db.py").write_text(
        "def get_user(name):\n"
        "    return execute('SELECT * FROM users WHERE name = ' + name)\n"
        "def execute(sql):\n"
        "    return cursor(sql)\n")
    issues = posture.scan_project(str(tmp_path))
    cross = [i for i in issues if i["type"] == "CROSS_FILE_TAINT"]
    assert cross, issues  # interprocedural flow must be surfaced
    assert "views.py" in cross[0]["file"] or "db.py" in cross[0]["file"]


def test_scan_surfaces_a10_error_handling(tmp_path):
    # A swallowed-exception (fail-open) must surface as an A10 finding with a
    # severity, alongside any precise-issues findings, in the posture scan.
    (tmp_path / "app.py").write_text(
        "def auth(request):\n"
        "    try:\n"
        "        ok = check_auth(request)\n"
        "    except Exception:\n"
        "        pass  # swallowed: caller proceeds as success\n"
        "    return ok\n")
    issues = posture.scan_project(str(tmp_path))
    a10 = [i for i in issues if i.get("detector") == "error_handling"]
    assert a10 and a10[0]["type"] == "SWALLOWED", issues
    assert "severity" in a10[0]  # posture needs a severity to grade
