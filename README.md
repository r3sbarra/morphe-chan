# Morphē-chan (モルフェ・ちゃん)

<p align="center">
  <img src="assets/morphe_chan_logo.png" alt="Morphē-chan Logo" width="320" />
</p>

**Programming expressed as multi-dimensional geometric vectors with properties
and compositing compound shapes, for code analysis, synthesis, bug detection,
and efficiency analysis.**

> Formerly **Code-Shape Research**. Morphē (μορφή) is Greek for *form / shape* —
> the project extracts the essential geometric form of code.

A zero-dependency, pure-Python research project that represents code as
multi-dimensional geometric vectors. Each function/class/program gets a shape
vector capturing intent, structure, efficiency, flow, libraries, algorithms,
patterns, vulnerabilities, and derived risk — enabling analysis, synthesis,
and security assessment.

## Features

- **Code-agnostic shape** — 13 language adapters (Python, JS, TS, Java, C,
  C++, C#, Go, Rust, Ruby, PHP, Swift, Kotlin)
- **Multi-dimensional shape** — 45-53 dims (primitives, efficiency, flow,
  libraries, algorithms, patterns, vulns, properties, derived values)
- **Algorithm detection** — binary search, sort, recursion, etc. from shape
  sequences
- **Pattern detection** — design patterns, data structures, concurrency,
  resilience
- **Vulnerability detection** — SQLi, XSS, RCE, SSRF, weak crypto, etc.
- **Type-aware shape** — param/variable shape enrichment with smart type inference (AST-based for Python), type profiles, and cross-function type-flow cascade + bug detection
- **Code synthesis** — simple functions, complex algorithms, and classes
- **Efficiency derivation** — from the enriched shape (O(log n), O(n log n), etc.)
- **Project analysis** — composite vectors, congestion, broken flows, health

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from code_shape import shape, true_similarity

# Get a function's shape
s = shape("def add(a, b):\n    return a + b")
print(s)  # RETURN>ARITH_ADD

# Compare two functions
sim = true_similarity(
    "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
    "def total(nums):\n    acc = 0\n    for v in nums:\n        acc += v\n    return acc",
)
print(sim)  # ~0.9

# Cross-language / cross-rename clone similarity via the PRIM:* core
from code_shape import primitive_similarity
x = primitive_similarity(
    "def add(a, b): return a + b",
    "fn add(a: i32, b: i32) -> i32 { a + b }", "python", "rust",
)
print(x)  # ~1.0 (same logical fn, rename- + language-invariant)
```

## CLI

The CLI is registered as the `morphe-chan` command (see `pyproject.toml`
`[project.scripts]`). After `pip install -e .` you can run it directly; or
invoke via `python3 src/cli.py` from the repo root.

```bash
morphe-chan shape <code-or-file> [--lang LANG] [--report]
morphe-chan analyze <code-or-file> [--lang LANG] [--report]
morphe-chan enriched <code-or-file> [--lang LANG] [--report]
morphe-chan algorithms <code-or-file> [--lang LANG] [--report]
morphe-chan patterns <code-or-file> [--lang LANG] [--report]
morphe-chan vulns <code-or-file> [--lang LANG] [--report]
morphe-chan efficiency <code-or-file> [--lang LANG] [--report]
morphe-chan project <dir> [--report]
morphe-chan anomalies <dir> [--lang LANG] [--k 2.0] [--limit 12]
morphe-chan imports <dir> [--file FILE]
morphe-chan compare <file-a> <file-b> [--report]
morphe-chan report <dir> [--format text|json|html|md]
morphe-chan languages
```

## Reports

Any analysis command with `--report` (or `report <dir> --format html|md`) writes a
**Markdown** report and an **interactive HTML** report (Chart.js graphs, vendored
locally for offline use) into a dated, typed folder:

```text
reports/<YYYY-MM-DD>/<analysis_type>/
  report.md     # portable Markdown report
  report.html   # interactive HTML report with graphs
  data.json     # raw analysis data
```

Example:

```bash
morphe-chan enriched src/cli.py --report
# → reports/2026-09-09/enriched/report.html

morphe-chan project . --report
# → reports/2026-09-09/project/report.html
```

The HTML report includes interactive bar, doughnut, and radar charts for the
enriched shape dimensions, efficiency signals, value-flow, algorithm/pattern
and vulnerability distributions, and the project composite vector.

## Project Structure

```
src/code_shape/
├── adapters/    # language adapters (13 languages)
├── core/        # shape models (flat, structural, composite, enriched)
├── analysis/    # algorithm/pattern/efficiency/flow detection
├── security/    # vulnerability/sink/exploitability detection
├── synthesis/   # code/algorithm/class synthesis
├── cli.py       # command-line interface
└── shape_analyzer.py  # object-oriented core
data/libraries/  # library shapes (versioned per language)
experiments/     # runnable experiments
research/        # research paper + reports
docs/            # documentation
```

## Experiments

All experiments are runnable: `python experiments/experiment_*.py`

| Experiment | Result |
|---|---|
| Clone detection | SHAPE model F1=0.818 |
| Code-agnostic | 13/13 languages |
| Cross-language clone | 14/14 accuracy |
| Bug-bounty detection | 20 CWE classes |
| Algorithm detection | binary_search, merge_sort, etc. |
| Efficiency derivation | O(log n), O(n log n) from shape |

## Research

- `research/RESEARCH.md` — the comprehensive research document (literature review, experiments, findings)

## Testing

```bash
python -m pytest tests/ -v
```

CI runs tests on every push via GitHub Actions (`.github/workflows/ci.yml`).

## License

MIT — see `LICENSE`.
