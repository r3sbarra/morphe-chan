"""Test suite for Morphē-chan (formerly code-shape-research).

Runs the core experiments as assertions to verify the system works.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape import shape, true_similarity, list_languages
from code_shape.core.enriched_shape import enriched_shape
from code_shape.analysis.algorithm_detector import detect_algorithm
from code_shape.analysis.pattern_detector import detect_patterns
from code_shape.analysis.enriched_efficiency import enriched_efficiency
from code_shape.security.precise_issues import find_precise_issues, find_buffer_overflows
from code_shape.synthesis.shape_library_synth import synthesize_any, synthesize_algorithm, synthesize_class


def test_languages():
    assert len(list_languages()) == 13


def test_shape():
    s = shape("def add(a, b):\n    return a + b")
    assert "RETURN" in s


def test_similarity():
    sim = true_similarity(
        "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
        "def total(nums):\n    acc = 0\n    for v in nums:\n        acc += v\n    return acc",
    )
    assert sim > 0.5


def test_enriched_shape():
    vec = enriched_shape("def f(x):\n    return x + 1")
    assert len(vec) > 20


def test_algorithm_detection():
    code = "def binary_search(arr, t):\n    lo, hi = 0, len(arr)-1\n    while lo <= hi:\n        mid = (lo+hi)//2\n        if arr[mid] == t:\n            return mid\n        elif arr[mid] < t:\n            lo = mid+1\n        else:\n            hi = mid-1\n    return -1"
    det = detect_algorithm(code)
    assert any(d["algorithm"] == "binary_search" for d in det)


def test_pattern_detection():
    code = "class Config:\n    _instance = None\n    def __new__(cls):\n        if cls._instance is None:\n            cls._instance = super().__new__(cls)\n        return cls._instance"
    det = detect_patterns(code)
    assert any(p["pattern"] == "singleton" for p in det)


def test_efficiency():
    r = enriched_efficiency("def binary_search(arr, t):\n    lo, hi = 0, len(arr)-1\n    while lo <= hi:\n        mid = (lo+hi)//2\n        if arr[mid] == t:\n            return mid\n        elif arr[mid] < t:\n            lo = mid+1\n        else:\n            hi = mid-1\n    return -1")
    assert r["complexity"] == "O(log n)"


def test_vuln_detection():
    code = "def f(request):\n    name = request.form['name']\n    return db.execute('SELECT * FROM users WHERE name = ' + name)"
    issues = find_precise_issues(code) + find_buffer_overflows(code)
    assert any(i["type"] == "SQL_INJECTION" for i in issues)


def test_synthesis_function():
    code = synthesize_any("fetch_api", "READ>TRANSFORM>RETURN", "python", "fetch")
    assert code is not None
    assert "requests.get" in code


def test_synthesis_algorithm():
    code = synthesize_algorithm("binary_search", "python", "bs")
    assert code is not None
    assert "while" in code


def test_synthesis_class():
    code = synthesize_class("singleton", "python", "Config")
    assert code is not None
    assert "class Config" in code
