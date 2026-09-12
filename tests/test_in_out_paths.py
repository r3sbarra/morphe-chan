"""tests/test_in_out_paths.py
Unit tests for trace_in_to_out_paths and format_paths_cli in code_shape.core.dataflow.
Verifies end-to-end dataflow paths from input parameters to outputs and sinks.
"""
import pytest
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from code_shape.core.dataflow import trace_in_to_out_paths, format_paths_cli


def test_in_to_out_simple_return():
    """Simple parameter to return statement flow."""
    code = """def add(a, b):
    total = a + b
    return total
"""
    paths = trace_in_to_out_paths(code)
    assert len(paths) >= 2  # one from 'a', one from 'b'
    
    # Check path from 'a'
    path_a = [p for p in paths if p["source"]["name"] == "a"][0]
    assert path_a["function"] == "add"
    assert path_a["sink"]["kind"] == "return"
    assert path_a["length"] == 3  # a -> total -> return
    assert "IN:PARAM[a]" in path_a["shape_sequence"]
    assert "OUT:RETURN" in path_a["shape_sequence"]
    assert path_a["is_vulnerable"] is False


def test_in_to_out_vulnerable_sink():
    """Tainted input flowing through intermediate assignments to dangerous sink."""
    code = """def get_user(request):
    name = request.args["name"]
    query = "SELECT * FROM users WHERE name = " + name
    return db.execute(query)
"""
    paths = trace_in_to_out_paths(code, file_path="src/api.py")
    assert len(paths) >= 1

    # Check sink path
    sink_paths = [p for p in paths if p["sink"]["name"] == "call:db.execute" or "db.execute" in p["sink"]["name"]]
    assert len(sink_paths) >= 1
    sp = sink_paths[0]
    assert sp["function"] == "get_user"
    assert sp["file"] == "src/api.py"
    assert sp["is_vulnerable"] is True
    assert sp["vulnerability_type"] == "SQL_INJECTION"
    assert sp["cwe"] == "CWE-89"
    assert "OUT:SINK[db.execute]" in sp["shape_sequence"]


def test_format_paths_cli():
    """format_paths_cli renders human-readable pathway blocks."""
    code = """def run(cmd):
    return os.system(cmd)
"""
    paths = trace_in_to_out_paths(code)
    formatted = format_paths_cli(paths)
    assert "[PATH 1]" in formatted
    assert "run()" in formatted
    assert "in:cmd" in formatted
    assert "out:" in formatted
    assert "Shape:" in formatted


def test_multi_function_separation():
    """Paths from different functions must be tagged with their respective function names."""
    code = """def fn1(x):
    return x * 2

def fn2(y):
    z = y + 10
    return z
"""
    paths = trace_in_to_out_paths(code)
    fns = {p["function"] for p in paths}
    assert "fn1" in fns
    assert "fn2" in fns
