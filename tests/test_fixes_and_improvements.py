import pytest
import sys
from pathlib import Path

# Ensure src is in sys.path
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "src" / "code_shape"))

from morphe_chan_mcp.server import _read_input as server_read_input, _dispatch
import importlib.util

_cli_path = _REPO / "src" / "cli.py"
_cli_spec = importlib.util.spec_from_file_location("root_cli", _cli_path)
_cli_module = importlib.util.module_from_spec(_cli_spec)
_cli_spec.loader.exec_module(_cli_module)
cli_read_input = _cli_module._read_input
from code_shape.security.precise_issues import find_precise_issues
from code_shape.synthesis.shape_library_synth import (
    synthesize_algorithm,
    synthesize_class,
    list_synthesis_intents,
    synthesize_any,
)


def test_read_input_long_code_snippets():
    """Verify that multi-line or long code (> 255 chars) does not trigger Errno 36 File name too long."""
    long_code = "def sample_function():\n" + "    value = 42\n" * 50
    assert len(long_code) > 255
    
    # Server _read_input
    assert server_read_input(long_code) == long_code
    
    # CLI _read_input
    assert cli_read_input(long_code) == long_code


def test_read_input_null_and_special_chars():
    """Verify weird strings and characters don't raise OSError/ValueError."""
    code_with_null = "SELECT * FROM users\0WHERE 1=1"
    assert server_read_input(code_with_null) == code_with_null
    assert cli_read_input(code_with_null) == code_with_null

    non_existent = "non_existent_file_path_12345.py"
    assert server_read_input(non_existent) == non_existent
    assert cli_read_input(non_existent) == non_existent


def test_read_input_valid_file(tmp_path):
    """Verify valid files are correctly read."""
    test_file = tmp_path / "hello.py"
    test_file.write_text("print('hello world')", encoding="utf-8")

    assert server_read_input(str(test_file)) == "print('hello world')"
    assert cli_read_input(str(test_file)) == "print('hello world')"


def test_vulns_detection_modern_interpolation():
    """Test vulnerability detection catches f-strings, format, %, and JS template literals."""
    # 1. SQLi via f-string
    sqli_fstring = 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")'
    issues = find_precise_issues(sqli_fstring)
    assert any(i["type"] == "SQL_INJECTION" for i in issues)

    # 2. SQLi via JS template literal
    sqli_js = 'db.query(`SELECT * FROM users WHERE id = ${user_id}`)'
    issues = find_precise_issues(sqli_js)
    assert any(i["type"] == "SQL_INJECTION" for i in issues)

    # 3. SQLi via .format()
    sqli_fmt = 'cursor.execute("SELECT * FROM users WHERE id = {}".format(uid))'
    issues = find_precise_issues(sqli_fmt)
    assert any(i["type"] == "SQL_INJECTION" for i in issues)

    # 4. SQLi via % formatting
    sqli_pct = 'cursor.execute("SELECT * FROM users WHERE id = \'%s\'" % uid)'
    issues = find_precise_issues(sqli_pct)
    assert any(i["type"] == "SQL_INJECTION" for i in issues)

    # 5. Path traversal via f-string
    path_fstring = 'open(f"/tmp/{user_filename}")'
    issues = find_precise_issues(path_fstring)
    assert any(i["type"] == "PATH_TRAVERSAL" for i in issues)

    # 6. SSRF via f-string
    ssrf_fstring = 'requests.get(f"https://{target_host}/status")'
    issues = find_precise_issues(ssrf_fstring)
    assert any(i["type"] == "SSRF" for i in issues)

    # 7. SSRF via template literal
    ssrf_js = 'fetch(`https://${host}/api`)'
    issues = find_precise_issues(ssrf_js)
    assert any(i["type"] == "SSRF" for i in issues)

    # 8. XSS via template literal
    xss_js = 'document.write(`<div>${name}</div>`)'
    issues = find_precise_issues(xss_js)
    assert any(i["type"] == "XSS" for i in issues)

    # 9. CMD injection via child_process / f-string
    cmd_fstring = 'os.system(f"ping -c 1 {host}")'
    issues = find_precise_issues(cmd_fstring)
    assert any(i["type"] == "CMD_INJECTION" for i in issues)


def test_vulns_parameterized_mitigation():
    """Verify parameterized queries are not flagged as SQL injection."""
    param_query = 'cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))'
    issues = find_precise_issues(param_query)
    assert not any(i["type"] == "SQL_INJECTION" for i in issues)


def test_multilingual_algorithm_synthesis():
    """Verify synthesis of algorithms in Python, JavaScript, and Go."""
    # Python
    py_code = synthesize_algorithm("binary_search", "python", "search")
    assert "def search(arr, target):" in py_code

    # JavaScript
    js_code = synthesize_algorithm("binary_search", "javascript", "search")
    assert "function search(arr, target) {" in js_code
    assert "Math.floor" in js_code

    # Go
    go_code = synthesize_algorithm("binary_search", "go", "Search")
    assert "func Search(arr []int, target int) int {" in go_code

    # Two sum
    assert "seen = {}" in synthesize_algorithm("two_sum", "python", "twoSum")
    assert "new Map()" in synthesize_algorithm("two_sum", "javascript", "twoSum")
    assert "make(map[int]int)" in synthesize_algorithm("two_sum", "go", "TwoSum")


def test_multilingual_class_synthesis():
    """Verify synthesis of design patterns and data structures in Python, JavaScript, and Go."""
    # Stack
    py_stack = synthesize_class("stack", "python", "Stack")
    assert "class Stack:" in py_stack

    js_stack = synthesize_class("stack", "javascript", "Stack")
    assert "class Stack {" in js_stack
    assert "this.items" in js_stack

    go_stack = synthesize_class("stack", "go", "Stack")
    assert "type Stack struct {" in go_stack
    assert "func (s *Stack) Push" in go_stack


def test_list_synthesis_intents_catalog():
    """Verify that intent catalog is complete and structured."""
    intents = list_synthesis_intents()
    assert "library_intents" in intents
    assert "algorithm_intents" in intents
    assert "class_patterns" in intents
    assert "shapes" in intents

    assert "binary_search" in intents["algorithm_intents"]
    assert "javascript" in intents["algorithm_intents"]["binary_search"]
    assert "go" in intents["algorithm_intents"]["binary_search"]

    assert "stack" in intents["class_patterns"]
    assert "go" in intents["class_patterns"]["stack"]


def test_mcp_server_dispatch():
    """Verify MCP server dispatching for new tools and edge cases."""
    # morphe_intents
    res_intents = _dispatch("morphe_intents", {})
    assert "algorithm_intents" in res_intents

    # morphe_synthesize with optional shape and default name
    res_synth = _dispatch("morphe_synthesize", {"intent": "binary_search", "lang": "javascript"})
    assert "function fn(arr, target)" in res_synth["code"]

    # morphe_shape with long inline snippet
    long_snippet = "def test():\n" + "    return 1\n" * 40
    shape_res = _dispatch("morphe_shape", {"code": long_snippet})
    assert isinstance(shape_res, str)
    assert len(shape_res) > 0
