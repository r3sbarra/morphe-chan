"""test_multilang_ast_dataflow.py — Comprehensive test suite for multi-language AST and dataflow.

Verifies:
  - Universal AST function & signature parsing across 13 languages.
  - Variable nodes, assignment data edges, call arguments, and return tracking.
  - Inter-procedural call graphs and data edges across functions.
  - In-to-out path tracing (trace_in_to_out_paths) on non-Python languages.
  - Enclosing function discovery (find_enclosing_function) with exact line boundaries.
  - Type-aware parameter and declaration inference.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.universal_ast import (
    extract_universal_functions,
    parse_universal_dfg,
    _parse_params,
)
from code_shape.core.dataflow import (
    project_dfg,
    trace_in_to_out_paths,
    dataflow_vector,
    dataflow_similarity,
)
from code_shape.core.type_aware_ast import _infer_types
from code_shape.security.precise_issues import find_enclosing_function, find_precise_issues


def test_param_parsing_across_languages():
    """Verify clean parameter names and type hint extraction across various language styles."""
    assert [(p.name, p.type_hint) for p in _parse_params("String input, int maxLen", "java")] == [
        ("input", "String"),
        ("maxLen", "int"),
    ]
    assert [(p.name, p.type_hint) for p in _parse_params("w http.ResponseWriter, r *http.Request", "go")] == [
        ("w", "http.ResponseWriter"),
        ("r", "*http.Request"),
    ]
    assert [(p.name, p.type_hint) for p in _parse_params("data: &str, count: usize", "rust")] == [
        ("data", "&str"),
        ("count", "usize"),
    ]
    assert [(p.name, p.type_hint) for p in _parse_params("char* dest, const char* src", "c")] == [
        ("dest", "char*"),
        ("src", "const char*"),
    ]
    assert [(p.name, p.type_hint) for p in _parse_params("user: string, id: number", "typescript")] == [
        ("user", "string"),
        ("id", "number"),
    ]
    assert [(p.name, p.type_hint) for p in _parse_params("string $user, int $id", "php")] == [
        ("user", "string"),
        ("id", "int"),
    ]
    assert [(p.name, p.type_hint) for p in _parse_params("query sql: String, count: Int", "swift")] == [
        ("sql", "String"),
        ("count", "Int"),
    ]
    assert [(p.name, p.type_hint) for p in _parse_params("sql, user_id", "ruby")] == [
        ("sql", None),
        ("user_id", None),
    ]


def test_javascript_ast_and_dataflow():
    code = """
function add(a, b) {
    const sum = a + b;
    return sum;
}

const doubleVal = (x) => {
    return add(x, x);
};

function main() {
    const val = 10;
    const res = doubleVal(val);
    console.log(res);
}
"""
    proj = project_dfg(code, lang="javascript")
    assert "add" in proj.functions
    assert "doubleVal" in proj.functions
    assert "main" in proj.functions

    add_dfg = proj.functions["add"]
    assert add_dfg.params == ["a", "b"]
    assert "sum" in add_dfg.vars
    assert any(e.src == "a" and e.dst == "sum" for e in add_dfg.edges)
    assert any(e.src == "b" and e.dst == "sum" for e in add_dfg.edges)
    assert any(e.src == "sum" and e.dst == "return" for e in add_dfg.edges)

    # Call edges
    assert ("doubleVal", "add") in proj.call_edges
    assert ("main", "doubleVal") in proj.call_edges

    # Inter-procedural data edges
    assert ("doubleVal", "add", "x") in proj.data_edges
    assert ("main", "doubleVal", "val") in proj.data_edges


def test_go_ast_and_dataflow():
    code = """
package main
import "fmt"

func Compute(a int, b int) int {
    total := a + b
    return total
}

func Run() {
    input := 42
    output := Compute(input, 100)
    fmt.Println(output)
}
"""
    proj = project_dfg(code, lang="go")
    assert "Compute" in proj.functions
    assert "Run" in proj.functions

    compute_fn = proj.functions["Compute"]
    assert compute_fn.params == ["a", "b"]
    assert "total" in compute_fn.vars
    assert any(e.src == "a" and e.dst == "total" for e in compute_fn.edges)
    assert ("Run", "Compute") in proj.call_edges
    assert ("Run", "Compute", "input") in proj.data_edges


def test_java_ast_and_dataflow():
    code = """
public class Service {
    public static int process(int a, int b) {
        int sum = a + b;
        return sum;
    }

    public static void main(String[] args) {
        int seed = 10;
        int result = process(seed, 20);
        System.out.println(result);
    }
}
"""
    proj = project_dfg(code, lang="java")
    assert "process" in proj.functions
    assert "main" in proj.functions

    proc_fn = proj.functions["process"]
    assert proc_fn.params == ["a", "b"]
    assert "sum" in proc_fn.vars
    assert ("main", "process") in proj.call_edges
    assert ("main", "process", "seed") in proj.data_edges


def test_c_and_cpp_ast_dataflow():
    code = """
#include <stdio.h>

int multiply(int x, int y) {
    int product = x * y;
    return product;
}

int main() {
    int factor = 5;
    int ans = multiply(factor, 10);
    printf("%d\\n", ans);
    return 0;
}
"""
    proj = project_dfg(code, lang="c")
    assert "multiply" in proj.functions
    assert "main" in proj.functions
    mul = proj.functions["multiply"]
    assert mul.params == ["x", "y"]
    assert "product" in mul.vars
    assert any(e.src == "product" and e.dst == "return" for e in mul.edges)
    assert ("main", "multiply") in proj.call_edges
    assert ("main", "multiply", "factor") in proj.data_edges


def test_rust_ast_and_dataflow():
    code = """
fn calculate(base: i32, multiplier: i32) -> i32 {
    let result = base * multiplier;
    return result;
}

fn main() {
    let arg = 15;
    let final_val = calculate(arg, 2);
    println!("{}", final_val);
}
"""
    proj = project_dfg(code, lang="rust")
    assert "calculate" in proj.functions
    assert "main" in proj.functions
    calc = proj.functions["calculate"]
    assert calc.params == ["base", "multiplier"]
    assert "result" in calc.vars
    assert ("main", "calculate") in proj.call_edges
    assert ("main", "calculate", "arg") in proj.data_edges


def test_ruby_and_php_ast_dataflow():
    ruby_code = """
def transform(data)
    cleaned = data
    return cleaned
end

def entry
    input = "test"
    out = transform(input)
    puts(out)
end
"""
    proj_rb = project_dfg(ruby_code, lang="ruby")
    assert "transform" in proj_rb.functions
    assert "entry" in proj_rb.functions
    assert ("entry", "transform") in proj_rb.call_edges

    php_code = """
<?php
function sanitizeInput($raw) {
    $clean = $raw;
    return $clean;
}
function handle() {
    $data = "unsafe";
    $res = sanitizeInput($data);
    echo $res;
}
"""
    proj_php = project_dfg(php_code, lang="php")
    assert "sanitizeInput" in proj_php.functions
    assert "handle" in proj_php.functions
    assert ("handle", "sanitizeInput") in proj_php.call_edges
    assert ("handle", "sanitizeInput", "data") in proj_php.data_edges


def test_in_to_out_paths_multi_language():
    """Verify in-to-out path tracing produces full multi-hop paths on non-Python code."""
    js_code = """
function executeSearch(query) {
    const sql = "SELECT * FROM items WHERE name = " + query;
    return db.query(sql);
}
"""
    paths = trace_in_to_out_paths(js_code, file_path="search.js", lang="javascript")
    assert len(paths) >= 1
    # Check vulnerable path leading into sink db.query
    vuln_paths = [p for p in paths if p.get("is_vulnerable")]
    assert len(vuln_paths) >= 1
    p = vuln_paths[0]
    assert p["function"] == "executeSearch"
    assert p["source"]["name"] == "query"
    assert any(h["kind"] == "assign" and h["node"] == "sql" for h in p["hops"])
    assert p["is_vulnerable"] is True
    assert p["vulnerability_type"] == "SQL_INJECTION"

    go_code = """
func RunCommand(cmdStr string) string {
    fullCmd := "/bin/sh -c " + cmdStr
    return exec.Command(fullCmd)
}
"""
    go_paths = trace_in_to_out_paths(go_code, file_path="runner.go", lang="go")
    assert len(go_paths) >= 1
    gp = go_paths[0]
    assert gp["function"] == "RunCommand"
    assert gp["source"]["name"] == "cmdStr"
    assert any(h["kind"] == "assign" and h["node"] == "fullCmd" for h in gp["hops"])


def test_enclosing_function_discovery_multilang():
    """Verify accurate enclosing function discovery and line bounds in non-Python files."""
    java_file = """package com.example;

public class Controller {
    public void index() {
        System.out.println("hello");
    }

    public void query(String user) {
        String sql = "SELECT * FROM users WHERE user = '" + user + "'";
        db.execute(sql);
    }
}
"""
    # Line 9 is inside 'query' function: db.execute(sql);
    enc = find_enclosing_function(java_file, line_no=9, lang="java")
    assert enc["name"] == "query"
    assert enc["start_line"] <= 8
    assert enc["end_line"] >= 10
    assert "db.execute(sql)" in enc["code"]
    assert enc["shape_part"] != "CLEAN"


def test_type_inference_multilang():
    """Verify explicit type declarations in typed languages are recognized."""
    typed_sample = """
void process(int count, String name, List<String> items, Map<String, Object> config) {
    int total = count + 1;
}
"""
    inferred = _infer_types(typed_sample, lang="java")
    assert inferred.get("count") == "INT"
    assert inferred.get("name") == "STR"
    assert inferred.get("items") == "LIST"
    assert inferred.get("config") == "DICT"
    assert inferred.get("total") == "INT"
