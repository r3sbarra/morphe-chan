"""Standalone MCP Server for Morphē-chan (multi-dimensional geometric code analysis).

Exposes the code-shape analysis engine (shape, enriched vectors, algorithms,
patterns, vulnerabilities, efficiency, synthesis, project analysis) as MCP
tools so agents (OpenClaw, Antigravity) can analyze and synthesize code.

Mirrors the falsci/lab-ass MCP server pattern.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Make the morphe-chan package importable when run from the repo root.
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "src" / "code_shape"))

from shape_analyzer import CodeShapeAnalyzer  # noqa: E402

server = Server("morphe-chan")
_analyzer = CodeShapeAnalyzer()


def _read_input(arg: str) -> str:
    """Read code from a file if arg is a file path, else treat as inline code."""
    if not arg or "\n" in arg or "\r" in arg or "\0" in arg or len(arg) > 4096:
        return arg
    try:
        p = Path(arg)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pass
    return arg


def _safe_json(obj: Any) -> Any:
    """Recursively coerce non-JSON-safe values (NaN/Inf) to strings."""
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(v) for v in obj]
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return str(obj)
        return obj
    return obj


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="morphe_shape",
            description="Get the human-readable shape signature of a code snippet or file (e.g. 'RETURN>ARITH_ADD').",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code snippet or file path"},
                    "lang": {"type": "string", "description": "Language hint (python, javascript, java, c, cpp, csharp, go, rust, ruby, php, swift, kotlin)"},
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="morphe_analyze",
            description="Full analysis of a code snippet: shape, structural, efficiency, value-flow, sinks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code snippet or file path"},
                    "lang": {"type": "string", "description": "Language hint"},
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="morphe_enriched",
            description="Full 45-53 dimensional shape vector: primitives, efficiency, flow, libraries, algorithms, patterns, vulns, properties, derived values.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code snippet or file path"},
                    "lang": {"type": "string", "description": "Language hint"},
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="morphe_algorithms",
            description="Detect algorithms (binary search, sort, recursion, etc.) from the shape sequence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code snippet or file path"},
                    "lang": {"type": "string", "description": "Language hint"},
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="morphe_patterns",
            description="Detect design, data-structure, concurrency, and resilience patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code snippet or file path"},
                    "lang": {"type": "string", "description": "Language hint"},
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="morphe_vulns",
            description="Detect security vulnerabilities mapped to MITRE CWE Top 25 & OWASP Top 10 with line numbers, exploitability scoring, and CVE references.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code snippet or file path"},
                    "lang": {"type": "string", "description": "Language hint"},
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="morphe_paths",
            description="Trace end-to-end dataflow paths from inputs to returns and dangerous sinks with geometric shape sequences.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code snippet or file path"},
                    "lang": {"type": "string", "description": "Language hint"},
                    "fn": {"type": "string", "description": "Optional function name to filter by"},
                    "vuln_only": {"type": "boolean", "description": "Only return paths reaching vulnerable sinks"},
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="morphe_efficiency",
            description="Derive time complexity (O(1), O(n), O(n^2), etc.) and efficiency signals.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code snippet or file path"},
                    "lang": {"type": "string", "description": "Language hint"},
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="morphe_synthesize",
            description="Generate code from an intent and shape signature (fetch_api, binary_search, singleton, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "description": "Intent (fetch_api, binary_search, singleton, etc.)"},
                    "shape": {"type": "string", "description": "Shape signature (READ>TRANSFORM>RETURN)"},
                    "lang": {"type": "string", "default": "python", "description": "Language (default python)"},
                    "name": {"type": "string", "description": "Optional function/class name"},
                },
                "required": ["intent"],
            },
        ),
        types.Tool(
            name="morphe_project",
            description="Full composite shape vector of an entire project (language distribution, primitives, functions, connections, sinks, imports).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "description": "Project directory"},
                },
                "required": ["dir"],
            },
        ),
        types.Tool(
            name="morphe_imports",
            description="Analyze the dependency/import graph of a project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "description": "Project directory"},
                    "file": {"type": "string", "description": "Dig into a specific file's imports"},
                },
                "required": ["dir"],
            },
        ),
        types.Tool(
            name="morphe_compare",
            description="Compare two code snippets by shape and structural similarity (0-1).",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "string", "description": "First code snippet or file"},
                    "b": {"type": "string", "description": "Second code snippet or file"},
                },
                "required": ["a", "b"],
            },
        ),
        types.Tool(
            name="morphe_languages",
            description="List the 13 supported programming languages.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="morphe_intents",
            description="List all supported synthesis intents, shapes, algorithms, and design patterns, along with supported languages.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        result = _dispatch(name, arguments)
        payload = _safe_json(result)
        return [types.TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]
    except Exception as exc:  # noqa: BLE001
        return [types.TextContent(type="text", text=f"ERROR: {type(exc).__name__}: {exc}")]


def _dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "morphe_shape":
        return _analyzer.shape(_read_input(args["code"]), args.get("lang"))
    if name == "morphe_analyze":
        return _analyzer.analyze(_read_input(args["code"]), args.get("lang"))
    if name == "morphe_enriched":
        from code_shape.core.enriched_shape import enriched_summary
        return enriched_summary(_read_input(args["code"]), args.get("lang"))
    if name == "morphe_algorithms":
        from code_shape.analysis.algorithm_detector import detect_algorithm
        return detect_algorithm(_read_input(args["code"]), args.get("lang")) or []
    if name == "morphe_patterns":
        from code_shape.analysis.pattern_detector import detect_patterns
        return detect_patterns(_read_input(args["code"]), args.get("lang")) or []
    if name == "morphe_vulns":
        raw = args["code"]
        target_file = raw if isinstance(raw, str) and not ("\n" in raw or len(raw) > 255) and Path(raw).is_file() else None
        code = _read_input(raw)
        lang = args.get("lang")
        from code_shape.security.precise_issues import find_precise_issues, find_buffer_overflows
        return find_precise_issues(code, file_path=target_file, lang=lang) + find_buffer_overflows(code, file_path=target_file, lang=lang)
    if name == "morphe_paths":
        raw = args["code"]
        target_file = raw if isinstance(raw, str) and not ("\n" in raw or len(raw) > 255) and Path(raw).is_file() else None
        code = _read_input(raw)
        lang = args.get("lang") or "python"
        from code_shape.core.dataflow import trace_in_to_out_paths
        paths = trace_in_to_out_paths(code, file_path=target_file, lang=lang)
        if args.get("fn"):
            paths = [p for p in paths if p.get("function") == args["fn"]]
        if args.get("vuln_only"):
            paths = [p for p in paths if p.get("is_vulnerable")]
        return paths
    if name == "morphe_efficiency":
        from code_shape.analysis.enriched_efficiency import enriched_efficiency
        return enriched_efficiency(_read_input(args["code"]), args.get("lang"))
    if name == "morphe_synthesize":
        from code_shape.synthesis.shape_library_synth import synthesize_any, synthesize_algorithm, synthesize_class
        lang = args.get("lang") or "python"
        fn_name = args.get("name") or "fn"
        shape_arg = args.get("shape") or ""
        code = synthesize_any(args["intent"], shape_arg, lang, fn_name)
        if not code:
            code = synthesize_algorithm(args["intent"], lang, fn_name)
        if not code:
            code = synthesize_class(args["intent"], lang, fn_name)
        return {"code": code} if code else {"error": f"cannot synthesize intent '{args['intent']}'"}
    if name == "morphe_project":
        return _analyzer.project_summary(args["dir"])
    if name == "morphe_imports":
        if args.get("file"):
            return _analyzer.dig_imports(args["dir"], args["file"])
        return _analyzer.project_imports(args["dir"])
    if name == "morphe_compare":
        ca, cb = _read_input(args["a"]), _read_input(args["b"])
        return {
            "shape_similarity": _analyzer.similarity(ca, cb),
            "structural_similarity": _analyzer.structural_similarity(ca, cb),
        }
    if name == "morphe_languages":
        return _analyzer.languages()
    if name == "morphe_intents":
        from code_shape.synthesis.shape_library_synth import list_synthesis_intents
        return list_synthesis_intents()
    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
