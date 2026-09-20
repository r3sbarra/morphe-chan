"""code_shape — Multi-dimensional geometric code analysis and synthesis.

A research project representing code as multi-dimensional geometric vectors
with properties and compositing compound shapes, for code analysis (clone
detection, bug detection, vulnerability detection, efficiency) and code
synthesis (function, algorithm, and class generation).

Subpackages:
  adapters   — language adapters (13 languages)
  core       — shape models (flat, structural, composite, enriched)
  analysis   — algorithm/pattern/efficiency/flow detection
  security   — vulnerability/sink/exploitability detection
  synthesis  — code/algorithm/class synthesis
"""
from .core.code_shape_core import (
    shape, true_shape_vector, true_similarity, primitive_similarity,
    recursive_shape, get_adapter, list_languages,
)
from .core.variable_shape import (
    infer_types, variable_shape, variable_shape_normalized,
    cascading_type_flow, merge_variable_shape, type_profile, type_profile_normalized,
)

from .chan import MorpheChan, morphe_chan

from .core.enriched_shape import enriched_shape, enriched_summary
from .core.fixed_shape import (
    fixed_enriched_shape, fixed_dim_count,
    merged_enriched_shape, STRUCTURAL_MERGES,
)

__version__ = "0.1.0"
__all__ = [
    "MorpheChan", "morphe_chan",
    "shape", "true_shape_vector", "true_similarity", "primitive_similarity",
    "recursive_shape", "get_adapter", "list_languages",
    "infer_types", "variable_shape", "variable_shape_normalized",
    "cascading_type_flow", "merge_variable_shape", "type_profile", "type_profile_normalized",
    "enriched_shape", "enriched_summary",
    "fixed_enriched_shape", "fixed_dim_count",
    "merged_enriched_shape", "STRUCTURAL_MERGES",
]
