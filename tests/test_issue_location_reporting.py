"""tests/test_issue_location_reporting.py
Verifies that detected issues retain and report exact location context:
File, Function/Method, Line, and Shape Part (geometric sub-shape signature).
Also tests Markdown and HTML report generation with location and shape part attribution.
"""
import pytest
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from code_shape.security.precise_issues import find_enclosing_function, find_precise_issues, find_buffer_overflows, issue_summary
from code_shape.reports.builder import collect_analysis
from code_shape.reports.markdown import render_markdown
from code_shape.reports.html import render_html


SAMPLE_MULTI_FUNC = '''import os

def helper(x):
    return x * 2

def run_command(request):
    cmd = request.args["cmd"]
    return os.system("ping " + cmd)

def calculate_sum(nums):
    total = 0
    for n in nums:
        total += n
    return total
'''


def test_find_enclosing_function_multi():
    """Verify enclosing function name, line bounds, and shape part are accurately resolved."""
    # Line 4 is inside helper
    enc_helper = find_enclosing_function(SAMPLE_MULTI_FUNC, 4, "python")
    assert enc_helper["name"] == "helper"
    assert enc_helper["start_line"] == 3
    assert enc_helper["end_line"] == 4
    assert len(enc_helper["shape_part"]) > 0

    # Line 8 is inside run_command
    enc_cmd = find_enclosing_function(SAMPLE_MULTI_FUNC, 8, "python")
    assert enc_cmd["name"] == "run_command"
    assert enc_cmd["start_line"] == 6
    assert enc_cmd["end_line"] == 8
    assert "RETURN" in enc_cmd["shape_part"] or "ARITH" in enc_cmd["shape_part"]

    # Line 12 is inside calculate_sum
    enc_sum = find_enclosing_function(SAMPLE_MULTI_FUNC, 12, "python")
    assert enc_sum["name"] == "calculate_sum"
    assert enc_sum["start_line"] == 10
    assert enc_sum["end_line"] == 14


def test_find_enclosing_function_module_level():
    """Module-level / top-level code defaults to <module>."""
    top_code = "import os\nos.system('ls')"
    enc = find_enclosing_function(top_code, 2, "python")
    assert enc["name"] == "<module>"
    assert enc["start_line"] == 1
    assert enc["shape_part"] is not None


def test_precise_issues_location_fields():
    """Issues returned by find_precise_issues must include file, function, shape_part, and path."""
    issues = find_precise_issues(SAMPLE_MULTI_FUNC, file_path="src/network.py", lang="python")
    assert len(issues) >= 1
    cmd_issue = [i for i in issues if i["type"] == "CMD_INJECTION"][0]

    assert cmd_issue["file"] == "src/network.py"
    assert cmd_issue["function"] == "run_command"
    assert cmd_issue["function_lines"] == [6, 8]
    assert cmd_issue["line"] == 8
    assert len(cmd_issue["shape_part"]) > 0
    assert "request" in cmd_issue["path"] or "cmd" in cmd_issue["path"]


def test_buffer_overflow_location_fields():
    """Buffer overflows must also include file, function, and shape_part."""
    code = "def get_item(arr, idx):\n    return arr[idx]"
    issues = find_buffer_overflows(code, file_path="src/utils.py", lang="python")
    assert len(issues) == 1
    bo = issues[0]
    assert bo["file"] == "src/utils.py"
    assert bo["function"] == "get_item"
    assert bo["shape_part"] is not None
    assert bo["path"] is not None


def test_issue_summary_includes_function_and_shape():
    """Human-readable summary must include function name and shape tag."""
    summary = issue_summary(SAMPLE_MULTI_FUNC, file_path="src/network.py", lang="python")
    assert "in run_command()" in summary
    assert "shape=" in summary


def test_markdown_report_renders_location_and_shape():
    """Markdown reports must render Location, Shape Part, and In-to-Out Paths."""
    rep = collect_analysis("vulns", "sample_target", code=SAMPLE_MULTI_FUNC, lang="python")
    md = render_markdown(rep)
    
    assert "## Vulnerabilities / Security Findings" in md
    assert "Location" in md
    assert "Shape Part" in md
    assert "`run_command()`" in md
    assert "## In-to-Out Dataflow Paths" in md
    assert "`request`" in md


def test_html_report_renders_location_and_shape():
    """HTML reports must include location and shape badges in vulnerability table."""
    rep = collect_analysis("vulns", "sample_target", code=SAMPLE_MULTI_FUNC, lang="python")
    html = render_html(rep)

    assert "Location" in html
    assert "Shape Part" in html
    assert "run_command()" in html
