# API Reference

## `code_shape` (top-level)

| Function | Description |
|---|---|
| `shape(code, lang=None)` | Human-readable shape of a code snippet |
| `true_shape_vector(code, lang=None)` | Normalized shape vector (recursive true shape) |
| `true_similarity(a, b, lang_a, lang_b)` | Cross-language shape similarity |
| `recursive_shape(code, lang)` | Recursive primitive decomposition |
| `get_adapter(code, lang)` | Get the language adapter |
| `list_languages()` | List supported languages |

## `code_shape.core`

| Module | Description |
|---|---|
| `code_shape_core` | Code-agnostic shape (13 adapters + recursive true shape) |
| `structural_shape` | AST-like tree shape (preserves nesting/order) |
| `composite_vector` | Full composite shape vector of a project |
| `enriched_shape` | 45-53 dim multi-dimensional shape |
| `new_shape_dims` | STATE/DATA/CTRL/IFACE/RES dimensions |
| `value_flow_shape` | Inputs/outputs through vector dimensions |
| `multilingual_project` | Multi-lingual project analysis |
| `import_analysis` | Import/dependency analysis |
| `program_shape` | Program decomposition (function shapes + call graph) |
| `type_aware_ast` | Type-aware AST decomposition |
| `variable_shape` | Param/variable shape enrichment + smart type inference |

### `code_shape.core.variable_shape`

| Function | Description |
|---|---|
| `infer_types(code, lang='python')` | Smart type inference: AST-based for Python (annotations, generics, assignment RHS, call-return, usage refinement), regex fallback for other languages. Returns `{var: bucket}`. |
| `variable_shape(code, lang)` | Per-identifier shape: `PARAM:<name>:<TYPE>`, `VAR:<name>:<TYPE>`, role dims (IN/OUT/INOUT), aggregates (PARAM_COUNT, VAR_COUNT, TYPE_DIVERSITY, MUTATION, UNTYPED). |
| `variable_shape_normalized(code, lang)` | L2-normalized variable shape (for cosine comparison). |
| `type_profile(code, lang)` | Compact, rename-invariant representation: `TYPE_PROFILE:<BUCKET>`, `ROLE_PROFILE:<ROLE>`, aggregates. Robust for cross-function comparison. |
| `type_profile_normalized(code, lang)` | L2-normalized type profile. |
| `cascading_type_flow(code, lang)` | Cross-function type propagation across the call graph + type-error detection. Returns `{functions, calls, propagations, type_errors, swapped_params}`. |
| `merge_variable_shape(enriched, code, lang, weight)` | Merge variable shape dims into an enriched shape vector. |

**Type buckets:** `INT, FLOAT, NUM, STR, BOOL, LIST, DICT, SET, TUPLE, CALLABLE, CLASS, ORM, FILE, NONE, UNKNOWN`. Numeric buckets (INT/FLOAT/NUM) are mutually compatible for type-error detection.

**Bug-catching:** `cascading_type_flow` flags type errors when an argument's bucket is incompatible with the parameter's bucket (e.g. passing INT to a STR param, DICT to a LIST param). It propagates types transitively across the call graph, so a type error in a callee is caught at the caller. Semantic swaps of type-identical params (e.g. `divide(2,10)` vs `divide(10,2)`) are NOT detectable from coarse type buckets alone.

## `code_shape.analysis`

| Module | Description |
|---|---|
| `algorithm_detector` | Detect algorithms from shape sequences |
| `pattern_detector` | Detect design/data/concurrency patterns |
| `efficiency_shape` | Efficiency shape (complexity, loops, threading) |
| `efficiency_v2` | Algorithm-aware efficiency |
| `enriched_efficiency` | Efficiency from enriched shape |
| `empirical_complexity` | Empirical complexity measurement |
| `bug_detector` | Function-level bug detection |
| `program_bug_detector` | Program-level bug detection |
| `exec_verifier` | Execution-based verification |

## `code_shape.security`

| Module | Description |
|---|---|
| `precise_issues` | Precise vulnerability finding |
| `security_detector_v2` | Taint-flow vulnerability detection |
| `sink_recognizer` | Sink recognition by semantic role |
| `sink_shape_vector` | Data-driven sink classification |
| `semantic_sinks` | Semantic sink detection |
| `dangerous_intent` | Dangerous intent shape detection |
| `vuln_v2` | Library-shape + taint-flow vuln detection |
| `exploitability` | Exploitability scoring |
| `library_shapes` | Library/module shapes |

## `code_shape.synthesis`

| Module | Description |
|---|---|
| `shape_library_synth` | Shape + library synthesis (functions, algorithms, classes) |
| `code_synthesizer` | Function synthesis from shape |
| `program_synthesizer` | Program synthesis from composite shape |
| `shape_translator` | Shape-based code translation |
