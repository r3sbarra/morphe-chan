#!/usr/bin/env python
"""shape_analyzer.py — Object-oriented core for code-shape analysis.

The `CodeShapeAnalyzer` class encapsulates:
  - shape decomposition (flat, structural, recursive)
  - cross-language analysis
  - program/project composite shapes
  - efficiency, value-flow, sinks, imports
  - comparison (similarity)

This is the object-oriented entry point for the whole system.
"""
import math
from pathlib import Path
from typing import Dict, List, Optional


class CodeShapeAnalyzer:
    """Object-oriented interface to the code-shape research system."""

    def __init__(self):
        # lazy imports to keep init fast
        self._core = None
        self._structural = None
        self._efficiency = None
        self._value_flow = None
        self._sinks = None
        self._composite = None
        self._imports = None

    # ── lazy module loaders ────────────────────────────────────────────────
    def _load(self, name):
        import importlib
        return importlib.import_module(name)

    @property
    def core(self):
        if self._core is None:
            self._core = self._load("code_shape.core.code_shape_core")
        return self._core

    @property
    def structural(self):
        if self._structural is None:
            self._structural = self._load("code_shape.core.structural_shape")
        return self._structural

    @property
    def eff_mod(self):
        if self._efficiency is None:
            self._efficiency = self._load("code_shape.analysis.efficiency_shape")
        return self._efficiency

    @property
    def vf_mod(self):
        if self._value_flow is None:
            self._value_flow = self._load("code_shape.core.value_flow_shape")
        return self._value_flow

    @property
    def sink_mod(self):
        if self._sinks is None:
            self._sinks = self._load("code_shape.security.semantic_sinks")
        return self._sinks

    @property
    def composite(self):
        if self._composite is None:
            self._composite = self._load("code_shape.core.composite_vector")
        return self._composite

    @property
    def imports(self):
        if self._imports is None:
            self._imports = self._load("code_shape.core.import_analysis")
        return self._imports

    # ── shape decomposition ────────────────────────────────────────────────
    def shape(self, code: str, lang: str = None) -> str:
        """Human-readable shape of a code snippet."""
        return self.core.shape(code, lang)

    def shape_vector(self, code: str, lang: str = None) -> Dict[str, float]:
        """Normalized shape vector (recursive true shape)."""
        return self.core.true_shape_vector(code, lang)

    def structural_shape(self, code: str) -> str:
        """Structural (AST-like) shape signature."""
        return self.structural.structural_signature(code)

    def languages(self) -> List[str]:
        """List supported languages."""
        return self.core.list_languages()

    # ── comparison ─────────────────────────────────────────────────────────
    def similarity(self, code_a: str, code_b: str, lang_a: str = None, lang_b: str = None) -> float:
        """Cross-language shape similarity."""
        return self.core.true_similarity(code_a, code_b, lang_a, lang_b)

    def structural_similarity(self, code_a: str, code_b: str) -> float:
        """Structural (tree) similarity."""
        return self.structural.structural_similarity(code_a, code_b)

    # ── efficiency ──────────────────────────────────────────────────────────
    def efficiency(self, code: str) -> Dict:
        """Efficiency summary (complexity, loops, threading)."""
        return self.eff_mod.efficiency_summary(code)

    def efficiency_vector(self, code: str) -> Dict[str, float]:
        """Efficiency shape vector."""
        return self.eff_mod.efficiency_vector(code)

    # ── value flow ──────────────────────────────────────────────────────────
    def value_flow(self, code: str) -> Dict[str, float]:
        """Value-flow shape (inputs/outputs through dimensions)."""
        return self.vf_mod.value_flow_shape(code)

    def flow_path(self, code: str) -> str:
        """Human-readable data-flow path (IN -> FLOW -> OUT)."""
        return self.vf_mod.flow_path(code)

    # ── sinks ──────────────────────────────────────────────────────────────
    def sinks(self, code: str) -> List[Dict]:
        """Detect dangerous sinks by semantic role."""
        return self.sink_mod.detect_sinks(code)

    def sink_shape(self, code: str) -> Dict[str, float]:
        """Sink-aware shape."""
        return self.sink_mod.sink_shape(code)

    # ── project analysis ───────────────────────────────────────────────────
    def project_composite(self, root: str) -> Dict[str, float]:
        """Full composite shape vector of an entire project."""
        return self.composite.composite_vector(Path(root))

    def project_summary(self, root: str) -> str:
        """Human-readable project composite summary."""
        return self.composite.composite_summary(Path(root))

    def project_imports(self, root: str) -> Dict:
        """Import analysis of a project (dependency graph)."""
        return self.imports.analyze_imports(Path(root))

    def dig_imports(self, root: str, file: str) -> Dict:
        """Dig down into a file's imports."""
        return self.imports.dig_imports(Path(root), file)

    # ── full analysis ──────────────────────────────────────────────────────
    def analyze(self, code: str, lang: str = None) -> Dict:
        """Full analysis of a code snippet: all dimensions."""
        return {
            "shape": self.shape(code, lang),
            "structural": self.structural_shape(code),
            "efficiency": self.efficiency(code),
            "value_flow": self.flow_path(code),
            "sinks": [s["category"] for s in self.sinks(code)],
        }


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    a = CodeShapeAnalyzer()
    print("=== CodeShapeAnalyzer (OOP core) ===")
    print("languages:", a.languages())
    code = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    print("shape:", a.shape(code))
    print("structural:", a.structural_shape(code))
    print("efficiency:", a.efficiency(code)["complexity"])
    print("flow:", a.flow_path(code))
    print("sinks:", a.sinks(code))
    print("full:", a.analyze(code))
