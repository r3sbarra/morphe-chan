#!/usr/bin/env python
"""cli.py — Command-line interface for Morphē-chan (code-shape analysis).

Usage:
  morphe-chan shape <code-or-file> [--lang LANG] [--report]
  morphe-chan analyze <code-or-file> [--lang LANG] [--report]
  morphe-chan enriched <code-or-file> [--lang LANG] [--report]
  morphe-chan algorithms <code-or-file> [--lang LANG] [--report]
  morphe-chan patterns <code-or-file> [--lang LANG] [--report]
  morphe-chan vulns <code-or-file> [--lang LANG] [--report]
  morphe-chan efficiency <code-or-file> [--lang LANG] [--report]
  morphe-chan synthesize <intent> <shape> [--lang LANG] [--name NAME]
  morphe-chan project <dir> [--report]
  morphe-chan imports <dir> [--file FILE]
  morphe-chan compare <file-a> <file-b>
  morphe-chan report <dir> [--format text|json|html|md]
  morphe-chan languages

Reports: any analysis command with `--report` (or `report <dir>`) writes a
Markdown + interactive HTML report to `reports/<YYYY-MM-DD>/<analysis_type>/`.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shape_analyzer import CodeShapeAnalyzer


def _read_input(arg: str) -> str:
    """Read code from a file if arg is a file, else treat as inline code."""
    p = Path(arg)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return arg


def _add_report_flag(p):
    """Add a --report flag to an analysis subparser."""
    p.add_argument("--report", action="store_true",
                   help="write an interactive HTML + Markdown report to reports/<date>/<type>/")
    return p


def _maybe_report(args, analysis_type, target, code=None, lang=None, project_dir=None, extra=None):
    """If --report was passed, build the dated/typed report and print its path."""
    if not getattr(args, "report", False):
        return None
    from code_shape.reports import build_report
    rep = build_report(analysis_type, target, code=code, lang=lang,
                       project_dir=project_dir, extra=extra)
    print(f"\n📄 Report written to: {rep.output_dir()}")
    print(f"   • {rep.output_dir() / 'report.md'}")
    print(f"   • {rep.output_dir() / 'report.html'}")
    print(f"   • {rep.output_dir() / 'report.mmd'}")
    # Print cascade diff if we have one
    diff = getattr(rep, "shape_diff", None)
    if diff is not None:
        from code_shape.memory import format_diff_cli
        print(format_diff_cli(diff))
    else:
        print('🌱 Morphē-chan: "First snapshot saved! Run again to track cascading changes, senpai! (◕‿◕✿)"')
    print('✨ Morphē-chan: "All done! Your geometric shape analysis is ready, senpai! (◕‿◕✿) ✦"')
    return rep


def main():
    from code_shape.art import ASCII_CLI_BANNER

    parser = argparse.ArgumentParser(
        prog="morphe-chan",
        description=(
            f"{ASCII_CLI_BANNER}\n\n"
            "Morphē-chan (モルフェ・ちゃん) — multi-dimensional geometric code analysis.\n"
            "Represents code as vectors (shape, efficiency, value-flow, "
            "algorithms, patterns, vulnerabilities) for analysis, synthesis, "
            "bug detection, and security assessment."
        ),
        epilog=(
            "Reports: any analysis command with --report (or 'report <dir> --format html|md') "
            "writes a Markdown + interactive HTML report to reports/<YYYY-MM-DD>/<type>/. "
            "\n\nExamples:\n"
            "  morphe-chan shape 'def add(a,b): return a+b'\n"
            "  morphe-chan enriched src/cli.py --report\n"
            "  morphe-chan project . --report\n"
            "  morphe-chan vulns src/app.py --lang python\n"
            "  morphe-chan compare a.py b.py"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="morphe-chan 0.1.0")
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<command>",
                                title="commands")

    # shape
    p = sub.add_parser("shape", help="Get the shape of a code snippet",
                       description="Print the human-readable shape signature of a code snippet or file.")
    p.add_argument("code", help="code snippet or file path")
    p.add_argument("--lang", default=None, help="language hint (python, javascript, java, ...)")
    _add_report_flag(p)

    # analyze
    p = sub.add_parser("analyze", help="Full analysis of a code snippet",
                       description="Run the full analysis: shape, structural, efficiency, value-flow, sinks.")
    p.add_argument("code", help="code snippet or file path")
    p.add_argument("--lang", default=None, help="language hint")
    _add_report_flag(p)

    # enriched
    p = sub.add_parser("enriched", help="Enriched multi-dimensional shape",
                       description="Full 45-53 dim shape: primitives, efficiency, flow, libraries, algorithms, patterns, vulns, properties, derived values.")
    p.add_argument("code", help="code snippet or file path")
    p.add_argument("--lang", default=None, help="language hint")
    _add_report_flag(p)

    # algorithms
    p = sub.add_parser("algorithms", help="Detect algorithms in code",
                       description="Detect algorithms (binary search, sort, recursion, ...) from the shape sequence.")
    p.add_argument("code", help="code snippet or file path")
    p.add_argument("--lang", default=None, help="language hint")
    _add_report_flag(p)

    # patterns
    p = sub.add_parser("patterns", help="Detect design/data/concurrency patterns",
                       description="Detect design, data-structure, concurrency, and resilience patterns.")
    p.add_argument("code", help="code snippet or file path")
    p.add_argument("--lang", default=None, help="language hint")
    _add_report_flag(p)

    # vulns
    p = sub.add_parser("vulns", help="Detect vulnerabilities in code",
                       description="Detect security vulnerabilities (SQLi, XSS, RCE, weak crypto, ...) with line numbers.")
    p.add_argument("code", help="code snippet or file path")
    p.add_argument("--lang", default=None, help="language hint")
    _add_report_flag(p)

    # efficiency
    p = sub.add_parser("efficiency", help="Efficiency analysis of a code snippet",
                       description="Derive time complexity (O(1), O(n), O(n^2), ...) and efficiency signals.")
    p.add_argument("code", help="code snippet or file path")
    p.add_argument("--lang", default=None, help="language hint")
    _add_report_flag(p)

    # synthesize
    p = sub.add_parser("synthesize", help="Synthesize code from intent + shape",
                       description="Generate code from an intent and shape signature (fetch_api, binary_search, singleton, ...).")
    p.add_argument("intent", help="intent (fetch_api, binary_search, singleton, etc.)")
    p.add_argument("shape", help="shape (READ>TRANSFORM>RETURN)")
    p.add_argument("--lang", default="python", help="language (default: python)")
    p.add_argument("--name", default="fn", help="function/class name (default: fn)")

    # project
    p = sub.add_parser("project", help="Composite shape of a project",
                       description="Full composite shape vector of an entire project (language distribution, primitives, functions, connections, sinks, imports).")
    p.add_argument("dir", help="project directory")
    _add_report_flag(p)

    # imports
    p = sub.add_parser("imports", help="Import analysis of a project",
                       description="Analyze the dependency/import graph of a project.")
    p.add_argument("dir", help="project directory")
    p.add_argument("--file", default=None, help="dig into a specific file's imports")

    # compare
    p = sub.add_parser("compare", help="Compare two code snippets",
                       description="Compare two code snippets by shape and structural similarity.")
    p.add_argument("a", help="first code or file")
    p.add_argument("b", help="second code or file")
    _add_report_flag(p)

    # report
    p = sub.add_parser("report", help="Full project report (shape, security, health)",
                       description="Generate a full project report. Use --format html|md to write a dated report folder with interactive graphs.")
    p.add_argument("dir", help="project directory")
    p.add_argument("--format", default="text", choices=["text", "json", "html", "md"],
                   help="output format (html/md write a dated report folder)")

    # banner
    sub.add_parser("banner", help="Display Morphē-chan cute anime ASCII mascot banner",
                   description="Display Morphē-chan cute anime ASCII mascot banner.")

    # snapshot
    p = sub.add_parser("snapshot", help="Save a shape snapshot of a file or project",
                       description="Save the current shape of a file or project dir to the local .morphe_snapshots/ memory.")
    p.add_argument("target", help="file path or project directory to snapshot")

    # diff
    p = sub.add_parser("diff", help="Show cascading shape changes since last snapshot",
                       description="Compare current shape against the most recent snapshot and show cascading diffs.")
    p.add_argument("target", help="file path or project directory to diff")

    # languages
    sub.add_parser("languages", help="List supported languages",
                   description="List the 13 supported programming languages.")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    a = CodeShapeAnalyzer()

    if args.cmd == "banner":
        print(ASCII_CLI_BANNER)

    elif args.cmd == "shape":
        code = _read_input(args.code)
        print(a.shape(code, args.lang))

    elif args.cmd == "analyze":
        code = _read_input(args.code)
        res = a.analyze(code, args.lang)
        print(f"shape:      {res['shape']}")
        print(f"structural: {res['structural']}")
        print(f"efficiency: {res['efficiency']['complexity']} "
              f"(loops={res['efficiency']['loops']}, nesting={res['efficiency']['nesting']})")
        print(f"value flow: {res['value_flow']}")
        print(f"sinks:      {res['sinks']}")
        _maybe_report(args, "analyze", args.code, code=code, lang=args.lang)

    elif args.cmd == "enriched":
        code = _read_input(args.code)
        from code_shape.core.enriched_shape import enriched_summary
        print(enriched_summary(code, args.lang))
        _maybe_report(args, "enriched", args.code, code=code, lang=args.lang)

    elif args.cmd == "algorithms":
        code = _read_input(args.code)
        from code_shape.analysis.algorithm_detector import detect_algorithm
        det = detect_algorithm(code, args.lang)
        if det:
            for d in det:
                print(f"  {d['algorithm']} (score={d['score']})")
        else:
            print("no algorithms detected")
        _maybe_report(args, "algorithms", args.code, code=code, lang=args.lang)

    elif args.cmd == "patterns":
        code = _read_input(args.code)
        from code_shape.analysis.pattern_detector import detect_patterns
        det = detect_patterns(code, args.lang)
        if det:
            for d in det:
                print(f"  {d['pattern']} (score={d['score']})")
        else:
            print("no patterns detected")
        _maybe_report(args, "patterns", args.code, code=code, lang=args.lang)

    elif args.cmd == "vulns":
        code = _read_input(args.code)
        from code_shape.security.precise_issues import find_precise_issues, find_buffer_overflows
        issues = find_precise_issues(code) + find_buffer_overflows(code)
        if issues:
            for i in issues:
                print(f"  {i['type']}@L{i['line']} sink={i['sink']}")
        else:
            print("no vulnerabilities detected")
        _maybe_report(args, "vulns", args.code, code=code, lang=args.lang)

    elif args.cmd == "efficiency":
        code = _read_input(args.code)
        from code_shape.analysis.enriched_efficiency import enriched_efficiency
        r = enriched_efficiency(code, args.lang)
        print(f"complexity: {r['complexity']} (method={r['method']})")
        print(f"loops: {r['loops']}, nesting: {r['nesting']}")
        _maybe_report(args, "efficiency", args.code, code=code, lang=args.lang)

    elif args.cmd == "synthesize":
        from code_shape.synthesis.shape_library_synth import synthesize_any, synthesize_algorithm, synthesize_class
        code = synthesize_any(args.intent, args.shape, args.lang, args.name)
        if not code:
            code = synthesize_algorithm(args.intent, args.lang, args.name)
        if not code:
            code = synthesize_class(args.intent, args.lang, args.name)
        if code:
            print(code)
        else:
            print(f"cannot synthesize intent '{args.intent}'")

    elif args.cmd == "project":
        print(a.project_summary(args.dir))
        _maybe_report(args, "project", args.dir, project_dir=args.dir)

    elif args.cmd == "imports":
        if args.file:
            res = a.dig_imports(args.dir, args.file)
            print(f"file: {res['file']}")
            print(f"imports: {res['imports']}")
            print(f"imported_by: {res['imported_by']}")
        else:
            res = a.project_imports(args.dir)
            print(f"imports: {res['import_count']}, unique: {res['unique_modules']}, "
                  f"files: {res['files_with_imports']}")

    elif args.cmd == "compare":
        ca, cb = _read_input(args.a), _read_input(args.b)
        sim = a.similarity(ca, cb)
        ssim = a.structural_similarity(ca, cb)
        print(f"shape similarity: {sim:.3f}")
        print(f"structural sim:   {ssim:.3f}")
        _maybe_report(args, "compare", f"{args.a} vs {args.b}",
                      code=ca, lang=None,
                      extra={"comparison": {"shape_similarity": sim, "structural_similarity": ssim}})

    elif args.cmd == "report":
        if args.format in ("html", "md"):
            from code_shape.reports import build_report
            rep = build_report("project", args.dir, project_dir=args.dir)
            print(f"📄 Report written to: {rep.output_dir()}")
            print(f"   • {rep.output_dir() / 'report.md'}")
            print(f"   • {rep.output_dir() / 'report.html'}")
            print(f"   • {rep.output_dir() / 'report.mmd'}")
            print('✨ Morphē-chan: "Project shape mapped! Geometry has truth, senpai! (◕‿◕✿) ✦"')
        else:
            report = _project_report(args.dir)
            if args.format == "json":
                print(json.dumps(report, indent=2))
            else:
                for k, v in report.items():
                    print(f"{k}: {v}")

    elif args.cmd == "languages":
        print(", ".join(a.languages()))


    elif args.cmd == "snapshot":
        _cmd_snapshot(args.target)

    elif args.cmd == "diff":
        _cmd_diff(args.target)


def _cmd_snapshot(target: str) -> None:
    """Save a shape snapshot for a file or project dir."""
    from code_shape.memory import SnapshotStore, ShapeSnapshot
    from code_shape.reports.builder import collect_analysis
    from datetime import datetime

    p = Path(target).resolve()
    is_project = p.is_dir()

    print(f"\n⬡ Morphē-chan: Capturing shape snapshot for: {target} ...")
    try:
        if is_project:
            rep = collect_analysis("project", target, project_dir=target)
        else:
            code = p.read_text(encoding="utf-8", errors="replace") if p.exists() else target
            rep = collect_analysis("enriched", target, code=code)
    except Exception as e:
        print(f"  Error collecting analysis: {e}")
        return

    from code_shape.memory import snapshot_from_report
    snap_root = p if is_project else p.parent
    store = SnapshotStore(snap_root)
    snap = snapshot_from_report(rep)
    store.save(snap)
    print(f"  ✅ Snapshot saved to: {snap_root / '.morphe_snapshots'}/")
    print(f"  📅 Timestamp: {snap.timestamp}")
    print(f"  📐 Enriched dims: {len(snap.enriched)}, complexity: {snap.complexity or 'n/a'}")
    print('✨ Morphē-chan: \"Snapshot saved! I\'ll remember this shape, senpai! (◕‿◕✿) ✦\"')


def _cmd_diff(target: str) -> None:
    """Show cascading shape diff vs. the last snapshot."""
    from code_shape.memory import SnapshotStore, snapshot_from_report, diff_snapshots, format_diff_cli
    from code_shape.reports.builder import collect_analysis

    p = Path(target).resolve()
    is_project = p.is_dir()
    snap_root = p if is_project else p.parent

    store = SnapshotStore(snap_root)
    old_snap = store.load_latest(target)
    if old_snap is None:
        print(f"\n⬡ Morphē-chan: No previous snapshot found for: {target}")
        print('  Run `morphe-chan snapshot <target>` first, or use --report to auto-snapshot, senpai!')
        return

    print(f"\n⬡ Morphē-chan: Computing cascading diff for: {target} ...")
    try:
        if is_project:
            rep = collect_analysis("project", target, project_dir=target)
        else:
            code = p.read_text(encoding="utf-8", errors="replace") if p.exists() else target
            rep = collect_analysis("enriched", target, code=code)
    except Exception as e:
        print(f"  Error collecting analysis: {e}")
        return

    new_snap = snapshot_from_report(rep)
    store.save(new_snap)
    diff = diff_snapshots(old_snap, new_snap)
    print(format_diff_cli(diff))


def _project_report(dirpath: str) -> dict:

    """Build a full project report: shape, security, health."""
    from code_shape.core.composite_vector import composite_vector
    from code_shape.core.enriched_shape import enriched_shape
    from pathlib import Path
    import re, os

    root = Path(dirpath)
    report = {
        "project": root.name,
        "composite_dims": len(composite_vector(root)),
    }
    # security signals
    sec = 0
    for dirpath2, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            try:
                code = (Path(dirpath2) / fn).read_text(errors="replace")
            except Exception:
                continue
            if re.search(r"hashlib\.md5|hashlib\.sha1|password\s*=\s*[\"'][^\"']+[\"']|\beval\s*\(|SELECT.*\+.*\w+", code):
                sec += 1
    report["security_signals"] = sec
    return report


if __name__ == "__main__":
    main()
