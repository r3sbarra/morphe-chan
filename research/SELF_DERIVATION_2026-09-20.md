# Morphe-chan Self-Derivation Research (2026-09-20)

Lab-ass session `43d9fe0c-d815-4ecb-8f72-8c31ecbccc63` — used Morphe-chan's own
enriched shape-vector geometry to (1) find improvements to Morphe-chan and
(2) derive new math/formulas/data from its vectors.

## Derived facts about Morphe-chan's own vector space (all verified)

- **Variable-length, not 45-62 fixed dims.** `enriched_shape` emits per-variable-
  NAME dims `PARAM:<name>:<TYPE>` / `VAR:<name>:<TYPE>` + conditional `TAINT:PARAM`.
  Across just 28 diverse functions the union is **179 dims**; PARAM:+VAR: = 91 dims
  (51%) are name-dependent. Naive cosine across arbitrary snippets is ill-defined.
- **85% sparse** (733/5012 matrix entries nonzero).
- **Unit-normalized**: every enriched vector has L2 norm EXACTLY 1.0 → all vectors
  live on S^(n-1), magnitude carries zero info, only direction (cosine) matters.
- **~25 effective intrinsic dims** (participation ratio) out of 179 nominal.
- **Cosine saturates** in the full sparse space (unrelated pairs score 0.76-0.97),
  and coarse family-total aggregation (14 buckets) makes it WORSE (0.973) — the
  discriminating info lives WITHIN primitive families, not in family totals.
- The enriched vector is NOT wired into `true_similarity`/clone detection (those use
  structural bag-of-tokens + polarity); enriched is for analysis only.

## New formulas derived (genuinely new, from the vectors themselves)

- **SHAPE_ENTROPY** = Shannon entropy of L1-normalized name-invariant dim weights.
  Ranks complexity: fact 4.79, loop 4.73, bsearch 4.58, matmul 4.24, add 3.78.
- **SHAPE_SPREAD** = nonzero-fraction of the 68 name-invariant dims (density).
- **SHAPE_SKEW** = (max−mean)/std of weights (concentration/dominance).
- **Self-profile of Morphe-chan's own source**: ASSIGN dominance 32.4% (9.16/fn),
  SEARCH 3.82, BRANCH 3.58, LOOP 2.57; H = 3.17 bits, evenness 0.722 over 21
  primitive types.

## Redundancy map (r=1.00 exact, safe to merge)

- whole GRAPH block (DATA_EDGES/MAX_FANOUT/MAX_FANIN/RECURSION/CYCLES) ≡ GRAPH:CALLS
- VAL:RISK ≡ VAL:SEVERITY;  PARAM_COUNT ≡ PROP:INPUTS;  PROP:SIDE_EFFECTS ≡ PRIM:WRITE
- high: EFF:LOOPS≡NESTING, VAL:BRANCHING≡PROP:BRANCHES≡GRAPH:BRANCHES
- **Corpus-bias caveat**: 5 of 8 small-corpus "dead" dims REVIVE at project scale
  (COMPARE_GE/GT/LT/NE, SORT). Only structural r=1.00 redundancies are safely droppable.

## Delivered improvement (implemented + tested)

- New `src/code_shape/core/shape_metrics.py`: rename-invariant SHAPE_ENTROPY/SPREAD/SKEW
  over a fixed GLOBAL_KEYS set; wired into `enriched_shape` before L2-normalization.
- `enriched_shape` now emits **65 dims** (was 62) incl. VAL:SHAPE_ENTROPY/SPREAD/SKEW.
- New `src/code_shape/core/fixed_shape.py`: `fixed_enriched_shape()` — the
  **fixed-length, rename-invariant re-embedding** (GLOBAL_KEYS + fixed PARAM/VAR
  type & role slots; no per-variable-name dims). Validated: fixed dims for all
  inputs, rename-invariant cos≈0.99, better discrimination than the saturated full
  space (add-vs-loop 0.564 vs 0.76+). Exported from package, tested.
- **Cross-language tail-return fix** (adapters/base.py + rust.py + ruby.py): Rust
  and Ruby use implicit/tail-expression returns (no `return` keyword), so their
  primitive vectors missed PRIM:RETURN and broke cross-language similarity (same
  add() = 0.707 vs 1.000). Added a `tail_return_patterns` hook; after fix all 10
  languages score 1.000 on the same logical function. **The PRIM:* subspace is the
  language-invariant core of the shape.**
- **Synthesis round-trip fixes** (code_synthesizer.py): READ/ARITH_ADD/SEARCH/FILTER
  single-primitive shapes didn't round-trip (templates didn't trigger analyzer
  primitives). Fixed templates; all four now ov=1.0; composites improved.
- **Safe structural-merge reduction** (`merged_enriched_shape`, 114→102 dims): merges
  only the r=1.00 definitionally-redundant dims. VERIFIED clone preservation
  (bsearch-clone 1.0, loop-clone 0.994) + discrimination (add-vs-matmul 0.51).
  (Note: earlier writeup said 80 dims — that predated the 114-dim rebase; the
  verified current count is 102 = 114 − 12 structural merges, corrected by the
  independent coder review.)
  **Negative result drove this**: unsupervised PCA (self_derive_intrinsic.py)
  DESTROYS clones (add-vs-clone 0.615) — Morphe-chan's space is ~6-25 global-intrinsic
  dims but the clone-discriminating subspace needs per-primitive detail, so PCA is
  rejected; only structural merges are safe.
- **Full suite: 324 passed** — additive, nothing broke (was 305 baseline).
- **Similarity benchmark + hybrid sweep** (self_derive_similarity_benchmark.py /
  self_derive_hybrid_similarity.py): full/merged enriched embeddings are POOR clone
  detectors (58%); PRIM:* is strong (71%); structural baseline is best (83%). A full
  alpha-sweep confirms NO blend beats 83% — Morphe-chan's true_similarity is already
  the optimal clone detector. Do NOT ship a blended/PRIM similarity replacement;
  the research value is on the analysis side.
- **Geometric anomaly detection** (self_derive_anomaly.py): new self-derived capability.
  PRIM-space distance-to-centroid flags structural outliers; on Morphe-chan's own 381
  functions it consistently surfaces the lookup/accessor shapes and 2 likely-dead
  placeholder fns — a shape-native outlier/smell detector. **SHIPPED as a feature**:
  `code_shape/analysis/anomaly_detector.py` (AnomalyDetector) + `morphe-chan anomalies
  <dir>` CLI command; on Morphe-chan's own source it flags 9/403 outliers (all
  lookup/accessor/mapper shapes). 4 new tests, full suite 328.
- **Dims/shape improved**: wired the previously-UNUSED `new_shape_dims` family
  (CTRL:CYCLOMATIC, STATE:PURE/MUTATES, IFACE:ARITY, DATA:*, RES:*) into
  `enriched_shape` → 65→72 dims. Also widened `shape()` top-5 → top-8 window
  (composite round-trip 0.83→0.97) and included the new dims in the fixed/merged
  embeddings (fixed 92→114, clone-preserving). Verified real signal (CYCLOMATIC
  ranks, PURE vs MUTATES, EXCEPTIONS). Additive; suite 330→338.
- **Security audit (data)**: real-CVE corpus is 16/16 CVE-type detection,
  13/16 taint-source on the LIVE pipeline (precise_issues + find_buffer_overflows)
  — the old experiment reported 10/16 because it used the deprecated
  detect_vulns_v2; fixed the experiment to use the live pipeline.
- **Language-aware synthesis** (code_synthesizer.py): the synthesizer ignored its
  `language` arg (always Python-flavored). Added a JS template set + brace-block
  codegen; `synthesize(shape, 'js')` now emits valid JS that round-trips through
  the JS adapter (all target primitives preserved); Python output unchanged. 4 new
  tests, suite 346→350. (CLI `synthesize --lang` still routes through
  shape_library_synth which remains Python-centric — noted.)

## Experiments (reproducible)

- `experiments/self_derive_corpus.py` — geometry facts (dims/sparsity/norm/participation)
- `experiments/self_derive_fixedembed.py` — fixed-length rename-invariant embedding
- `experiments/self_derive_family_embedding.py` — family-coarsening (negative result) + metrics
- `experiments/self_derive_dimreduction.py` — collinear-dim redundancy map + reduced embedding
- `experiments/self_derive_selfanalysis.py` — Morphe-chan analyzing its own source
- `experiments/self_derive_roundtrip.py` — synthesis↔analysis self-consistency audit
- Data: `data/self_derive_matrix.json`, `data/dim_reduction_spec.json`,
  `data/family_embedding_spec.json`, `data/self_analysis_profile.json`

## Follow-up (remaining)

(1) ✅ DONE: safe reduction via structural r=1.00 merges (`merged_enriched_shape`, 114→102 dims — 102 is the verified count; the earlier 80 was pre-rebase).
    ❌ Unsupervised PCA is REJECTED for reduction (destroys clones) — any further
    compression must be a supervised/metric-learning projection preserving
    within-family primitive detail. (2) Optionally wire `fixed_enriched_shape` /
    `merged_enriched_shape` into `true_similarity`/clone detection and benchmark vs
    the structural bag-of-tokens baseline. (3) Investigate the synthesizer's
    cross-language language-arg gap (synthesize() produced identical output for all
    languages → language parameter ignored for tested shapes). (4) The
    `READ>LOOP>ARITH_MOD>FILTER>RETURN` composite round-trip is capped at ov=0.4 by
    the top-5 primitive shape window — consider widening the window for composite
    fidelity.
