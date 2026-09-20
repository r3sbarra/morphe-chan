"""Regression tests for lexer-aware new_shape_dims.

The derived shape dims (STATE/DATA/CTRL/IFACE/RES) feed efficiency
classification, so false positives corrupt derived complexity. Confirmed
before the fix: a comment `print(` killed STATE:PURE, a string `"if we go"`
inflated CYCLOMATIC, and `data.get(...)` was misdetected as a network call.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.new_shape_dims import (
    state_dims, data_dims, control_dims, resource_dims, interface_dims,
)


def test_comment_print_does_not_kill_pure():
    d = state_dims('# print("hello") just a comment\ndef f():\n    return 1')
    assert d.get("STATE:PURE") == 1, d


def test_string_if_does_not_count_cyclomatic():
    d = control_dims('name = "if we go"\ndef f():\n    return name')
    assert d.get("CTRL:CYCLOMATIC", 0) == 1, d  # only the real `return`


def test_dict_get_is_not_network():
    d = resource_dims('data = request.POST\nname = data.get("name")')
    assert d.get("RES:NETWORK", 0) == 0, d


def test_request_json_is_not_network():
    d = resource_dims("data = request.json")
    assert d.get("RES:NETWORK", 0) == 0, d


def test_real_network_still_detected():
    assert resource_dims('r = requests.get(url)').get("RES:NETWORK") == 1
    assert resource_dims('f = urlopen(url)').get("RES:NETWORK") == 1
    assert resource_dims('fetch("/api")').get("RES:NETWORK") == 1


def test_real_mutation_and_global_detected():
    assert state_dims("x.append(1)").get("STATE:MUTATES") == 1
    assert state_dims("global g\ndef f():\n    return g").get("STATE:GLOBAL") == 1


def test_real_nested_data_detected():
    assert data_dims('xs = [{"a": 1}]').get("DATA:NESTED") == 1


def test_interface_arity():
    d = interface_dims("def f(a, b, c=3):\n    return a")
    assert d.get("IFACE:ARITY") == 3
    assert d.get("IFACE:DEFAULTS") == 1
