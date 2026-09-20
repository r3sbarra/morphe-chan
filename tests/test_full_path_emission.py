"""Tests for full source->sink data-flow path emission in morphe-chan."""

from code_shape.core.value_flow_shape import trace_taint_path
from code_shape.security.precise_issues import find_precise_issues


def test_trace_taint_path_reconstructs_chain():
    code = (
        "def handle(user_input):\n"
        "    payload = user_input\n"
        "    query = 'SELECT * FROM t WHERE id = ' + payload\n"
        "    cursor.execute(query)\n"
        "    return query\n"
    )
    path = trace_taint_path(code, "    cursor.execute(query)")
    # Full chain from source to sink: source -> user_input -> payload -> query -> sink
    joined = " -> ".join(str(h) for h in path)
    assert "PARAM" in joined
    assert "payload" in joined
    assert "query" in joined
    assert "cursor.execute" in joined


def test_precise_issues_emit_full_path():
    code = (
        "def handle(user_input):\n"
        "    payload = user_input\n"
        "    return cursor.execute(f\"SELECT * FROM u WHERE id = '{payload}'\")\n"
    )
    issues = find_precise_issues(code, lang="python")
    # SQL injection should carry a full path with hops.
    sqli = [i for i in issues if i["type"] == "SQL_INJECTION"]
    assert sqli, "expected an SQL injection finding"
    i = sqli[0]
    assert "path_hops" in i, "expected path_hops key"
    # The path must include the parameter, the intermediate var, and the sink call
    hops = [h.lower() for h in i["path_hops"]]
    assert any("payload" in h for h in hops), f"expected payload in hops, got {hops}"
    assert any(h == "param" or h.startswith("param") for h in hops), f"expected source param in hops, got {hops}"
