#!/usr/bin/env python
"""reports/__init__.py — Report generation for Morphē-chan analysis.

Generates per-analysis reports under `reports/<YYYY-MM-DD>/<analysis_type>/`:

  report.md   — Markdown report (portable, readable)
  report.html — Interactive HTML report with Chart.js graphs (offline)

The report builder collects every analysis dimension the project produces
(shape, enriched vector, efficiency, value-flow, algorithms, patterns,
vulnerabilities, composite project vector, imports) and renders them into
both formats.
"""
from code_shape.reports.builder import (
    AnalysisReport,
    build_report,
    collect_analysis,
    REPORT_ROOT,
)
from code_shape.reports.markdown import render_markdown
from code_shape.reports.html import render_html

__all__ = [
    "AnalysisReport",
    "build_report",
    "collect_analysis",
    "render_markdown",
    "render_html",
    "REPORT_ROOT",
]
