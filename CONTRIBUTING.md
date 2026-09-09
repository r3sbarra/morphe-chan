# Contributing to Morphē-chan

Thanks for your interest! This project represents code as multi-dimensional
geometric vectors for analysis and synthesis. Here's how to contribute.

## Getting Started

```bash
# Install in editable mode
pip install -e .

# Run the experiments
python experiments/experiment_*.py

# Use the CLI
morphe-chan shape "def add(a, b): return a + b"
```

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
```

## Adding a New Language Adapter

1. Create `src/code_shape/adapters/<lang>.py` with a `LanguageAdapter` subclass
2. Register it in `src/code_shape/adapters/__init__.py`
3. Add its library shapes to `data/libraries/<lang>/v1/libraries.json`

## Adding a New Algorithm/Pattern

1. Add the signature to `src/code_shape/analysis/algorithm_detector.py` or
   `pattern_detector.py` (key primitives + distinguishing features)
2. Add a synthesis template to `src/code_shape/synthesis/shape_library_synth.py`

## Code Style

- Pure Python stdlib only (no external dependencies)
- Docstrings on all public functions
- Falsifiable experiments (record results in `research/PAPER.md`)

## Testing

Run all experiments to verify nothing is broken:

```bash
for f in experiments/experiment_*.py; do python3 "$f"; done
```

## License

MIT — see `LICENSE`.
