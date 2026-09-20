"""Imports/analysis regression test for import_analysis.py.

The Go multi-import block form was captured as ONE broken string
('\t"fmt"\n\t"os"'), corrupting the composite vector's IMP: dims. Block-style
imports are now split into individual module tokens while preserving the
language-aware module paths (dots, backslashes, slashes).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.import_analysis import extract_imports, analyze_imports, import_vector


def test_go_import_block_split():
    go = 'import (\n    "fmt"\n    "os"\n    "net/http"\n)'
    got = extract_imports(go, "go")
    assert got == ["fmt", "os", "net/http"], got


def test_go_single_import():
    assert extract_imports('import "fmt"', "go") == ["fmt"]


def test_python_from_and_import():
    got = extract_imports('from utils import helper\nimport os', "python")
    assert "utils" in got and "os" in got


def test_java_nested_package_kept():
    assert extract_imports("import java.util.List;", "java") == ["java.util.List"]


def test_php_namespace_kept():
    assert extract_imports("use App\\Models\\User;", "php") == ["App\\Models\\User"]


def test_import_vector_counts_block_imports(tmp_path):
    from pathlib import Path as P
    (tmp_path / "main.go").write_text(
        'package main\nimport (\n    "fmt"\n    "os"\n)\nfunc main(){}')
    vec = import_vector(tmp_path)
    # IMP_COUNT must reflect the 2 individual Go modules, not 1 broken string.
    assert vec["IMP_COUNT"] == 2, vec
    assert vec["IMP_UNIQUE"] == 2, vec
