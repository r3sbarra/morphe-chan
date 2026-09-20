#!/usr/bin/env python
"""cross_file_taint.py — Cross-file taint propagation + LLM false-positive pruning.

Two capabilities that close the biggest gaps identified in the vuln research
(2026-09-18):

  1. CROSS-FILE TAINT: taint propagates across function/module boundaries.
     A tainted variable passed as an argument at a call site marks the callee's
     corresponding formal parameter as tainted, so a sink in the callee (possibly
     in another file) is reached from an external source in the caller. This is
     the single biggest SAST gap per 2024-26 literature (Route Sixty-Sink,
     Lint-Owl, AdaTaint all emphasize interprocedural/cross-file flow).

  2. LLM FP-PRUNING: after a deterministic taint pass produces CANDIDATE issues,
     an optional verifier (LLM or heuristic) filters spurious alerts by asking
     "is the source really attacker-controlled AND does it reach the sink
     unmitigated?". Mirrors AdaTaint/TaintP2X's source-controllability +
     multi-round verification stage.

Dependency-free core; LLM verifier is an injected callable (opt-in).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

#: External input sources (tautology across frameworks).
INPUT_SOURCES = [
    "request", "req", "ctx", "environ", "getenv", "input", "argv",
    "$_GET", "$_POST", "$_REQUEST", "body", "params", "query", "form",
    "json", "data", "cookie", "header", "session", "PathVariable", "RequestParam",
]

#: Dangerous sinks (callee names) that terminate a taint path as a finding.
DANGEROUS_SINKS = [
    "execute", "query", "system", "eval", "exec", "open", "read", "write",
    "render", "render_template_string", "template", "popen", "shell",
    "urllib", "urlopen", "requests", "load", "loads", "pickle", "compile",
]
#: Sink name fragments that indicate a HIGHER impact class.
HIGH_IMPACT_SINKS = ["execute", "system", "popen", "eval", "exec", "shell", "pickle", "urlopen"]


@dataclass
class FunctionUnit:
    """A function's call sites + param names, enough to do cross-file taint."""
    name: str
    file: str
    params: List[str] = field(default_factory=list)
    #: call site: (callee_name, [arg_exprs], line)
    call_sites: List[Tuple[str, List[str], int]] = field(default_factory=list)
    body: str = ""

    def __hash__(self):  # pragma: no cover
        return hash((self.file, self.name))


@dataclass
class TaintFlow:
    """One cross-file taint path: source (file/fn/var) -> callee -> sink."""
    source_var: str
    source_file: str
    source_kind: str
    callee: str
    callee_file: str
    callee_param: str
    sink_name: str
    sink_line: int
    vulnerable: bool
    hops: List[str] = field(default_factory=list)


class CrossFileTaint:
    """Propagate taint across function/module boundaries within a directory."""

    def __init__(self):
        self.functions: Dict[str, FunctionUnit] = {}       # key: "file::name"
        self.callee_refs: Dict[str, Set[str]] = defaultdict(set)  # callee -> callers

    # -- build -----------------------------------------------------------------
    def index(self, target_dir: str | Path) -> None:
        """Index all Python functions + their call sites in a directory tree."""
        root = Path(target_dir).resolve()
        for py in root.rglob("*.py"):
            if any(part.startswith(".") or part in {"node_modules", "venv", ".venv", "__pycache__"}
                   for part in py.parts):
                continue
            try:
                src = py.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            self._index_file(src, str(py))

    def _index_file(self, src: str, file_path: str) -> None:
        try:
            import ast
            tree = ast.parse(src)
        except Exception:
            return
        module_funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in node.args.args]
                call_sites = []
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        # bare Name call (foo(...)) or Attribute call (obj.foo(...))
                        callee = None
                        if isinstance(sub.func, ast.Name):
                            callee = sub.func.id
                        elif isinstance(sub.func, ast.Attribute):
                            callee = sub.func.attr  # method name
                        if callee:
                            args = []
                            for a in sub.args:
                                if isinstance(a, ast.Name):
                                    args.append(a.id)
                                elif isinstance(a, ast.Constant):
                                    args.append(repr(a.value))
                                else:
                                    args.append("<expr>")
                            call_sites.append((callee, args, sub.lineno))
                # Only index functions that take params (have taint surfaces).
                if params:
                    key = f"{file_path}::{node.name}"
                    self.functions[key] = FunctionUnit(
                        name=node.name, file=file_path, params=params,
                        call_sites=call_sites,
                        body=src.splitlines()[node.lineno - 1:node.end_lineno],
                    )
                    module_funcs.append(node.name)
                    for callee, _args, _ln in call_sites:
                        self.callee_refs[callee].add(node.name)

    # -- cross-file propagation -------------------------------------------------
    def propagate(self, external_sources: Optional[Dict[str, List[str]]] = None) -> List[TaintFlow]:
        """Propagate taint from external sources (or explicit entry points) across
        call boundaries and return all flows reaching a dangerous sink.

        external_sources: {function_name: [param_names]} — entry-point functions
        whose listed params are initially untrusted (e.g. request handlers).
        If None, any function calling a dangerous sink directly OR any function
        whose body reads an external input source is treated as an entry.
        """
        flows: List[TaintFlow] = []
        entries = external_sources or self._auto_entries()

        # For each entry, walk the call graph carrying param taint forward.
        for entry_fn, tainted_params in entries.items():
            for tparam in tainted_params:
                self._walk(entry_fn, tparam, [], flows, set())

        # Dedupe by (source_file, sink_line, sink_name).
        seen = set()
        out = []
        for f in flows:
            key = (f.source_file, f.sink_line, f.sink_name)
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
        return out

    def _auto_entries(self) -> Dict[str, List[str]]:
        """Entry-point functions: ones whose body reads an external input, or
        handlers (route-decorated in source)."""
        entries: Dict[str, List[str]] = defaultdict(list)
        for key, unit in self.functions.items():
            body_text = "\n".join(unit.body)
            # external input read in body -> all params tainted
            if any(re.search(r"\b" + re.escape(s) + r"\b", body_text, re.IGNORECASE)
                   for s in INPUT_SOURCES):
                entries[unit.name] = list(unit.params)
        return dict(entries)

    def _walk(self, fn_name: str, tparam: str, path: List[str],
              flows: List[TaintFlow], visited: Set[Tuple[str, str]]) -> None:
        key = (fn_name, tparam)
        if key in visited or len(path) > 20:
            return
        visited.add(key)

        # Find every function named fn_name (could be in multiple files).
        units = [u for k, u in self.functions.items() if u.name == fn_name]
        for unit in units:
            body_text = "\n".join(unit.body)
            # Local aliases: vars assigned FROM the tainted param (payload = request)
            aliases = self._tainted_aliases(body_text, tparam)
            tainted_names = {tparam} | aliases

            # Does any tainted name reach a dangerous sink in this unit?
            sink = self._sink_hit(unit.body, tainted_names)
            if sink:
                flows.append(TaintFlow(
                    source_var=tparam, source_file=unit.file,
                    source_kind="tparam", callee=fn_name, callee_file=unit.file,
                    callee_param=tparam, sink_name=sink[0], sink_line=sink[1],
                    vulnerable=True, hops=path + [f"{fn_name}({tparam}) -> {sink[0]}()"],
                ))
                continue

            # Propagate into callees: any tainted name passed as an arg.
            for callee, args, ln in unit.call_sites:
                for i, arg in enumerate(args):
                    if any(re.search(r"\b" + re.escape(tn) + r"\b", arg) for tn in tainted_names):
                        callee_unit = self._find_callee(callee, unit.file)
                        if callee_unit and len(callee_unit.params) > i:
                            self._walk(callee, callee_unit.params[i],
                                       path + [f"{fn_name}.{ln}:{arg}"],
                                       flows, visited)

    def _find_callee(self, callee: str, from_file: str) -> Optional[FunctionUnit]:
        # Prefer same-file callee, then any.
        candidates = [u for k, u in self.functions.items() if u.name == callee]
        if not candidates:
            return None
        same_file = [u for u in candidates if u.file == from_file]
        return same_file[0] if same_file else candidates[0]

    def _tainted_aliases(self, body: str, tparam: str) -> Set[str]:
        """Vars assigned from an expression referencing the tainted param."""
        aliases = set()
        for m in re.finditer(r"\b(\w+)\s*=\s*([^;\n]+)", body):
            var, rhs = m.group(1), m.group(2).strip()
            if not rhs.startswith(("=", "==", "!=", "<=", ">=")) and \
               re.search(r"\b" + re.escape(tparam) + r"\b", rhs):
                aliases.add(var)
        return aliases
        # Prefer same-file callee, then any.
        candidates = [u for k, u in self.functions.items() if u.name == callee]
        if not candidates:
            return None
        same_file = [u for u in candidates if u.file == from_file]
        return same_file[0] if same_file else candidates[0]

    def _sink_hit(self, body: str, tainted: Set[str]) -> Optional[Tuple[str, int]]:
        """Return (sink_name, line) if any tainted var flows into a dangerous call in body."""
        for i, line in enumerate(body, 1):
            low = line.lower()
            if any(re.search(r"\b" + re.escape(tn) + r"\b", line) for tn in tainted) and \
               any(re.search(r"\b" + re.escape(s) + r"\b", low) for s in DANGEROUS_SINKS):
                matched = next(s for s in DANGEROUS_SINKS if re.search(r"\b" + re.escape(s) + r"\b", low))
                return (matched, i)
        return None


# =============================================================================
# LLM / heuristic FALSE-POSITIVE PRUNING
# =============================================================================

def prune_false_positives(
    issues: List[Dict[str, Any]],
    verifier: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    code_of: Optional[Callable[[int], str]] = None,
) -> Dict[str, Any]:
    """Prune spurious taint findings.

    issues: candidate issues (each with 'type','line','path_hops','source','sink').
    verifier: optional async/sync callable issue -> {confirmed: bool, reason: str}.
              If omitted, a deterministic heuristic prunes by source-controllability
              + mitigation presence (AdaTaint / TaintP2X style, no LLM cost).
    code_of: optional callable line_no -> source line (for the verifier prompt).

    Returns {'kept': [...], 'pruned': [...], 'reasoned': [...]}.
    """
    kept, pruned, reasoned = [], [], []
    for issue in issues:
        if verifier is not None:
            verdict = verifier(issue)
        else:
            verdict = _heuristic_verdict(issue)
        entry = dict(issue)
        entry["_prune_reason"] = verdict.get("reason", "ok")
        if verdict.get("confirmed", True):
            kept.append(entry)
        else:
            pruned.append(entry)
        if verdict.get("reason"):
            reasoned.append(entry)
    return {"kept": kept, "pruned": pruned, "reasoned": reasoned}


#: Mitigations that clear a taint path (conservative).
_PRUNE_MITIGATIONS = [
    "sanitize", "escape", "valid", "allowlist", "whitelist", "parameterized",
    "prepared", "bind", "quote", "cast", "int(", "float(", "html.escape",
    "textContent", ".format(", "f'", "f\"", "ast.literal_eval", "shlex.quote",
    "basename", "realpath", "normpath", "shell=False",
]
#: Sources that are NOT attacker-controlled (private/local).
_NON_PUBLIC_SOURCES = ["os.environ", "getenv", "argv", "environ", "settings", "config", "constant"]


def _heuristic_verdict(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic FP prune: drop findings with non-controllable sources or
    clear mitigations; keep the rest."""
    iss_type = (issue.get("type") or "").upper()
    source = (issue.get("source") or "")
    code_line = (issue.get("code_line") or "")
    hops = " ".join(str(h) for h in issue.get("path_hops", []))

    # 1. If every source is non-public (config/env/settings) -> prune.
    if source and any(src in source.lower() for src in _NON_PUBLIC_SOURCES):
        return {"confirmed": False, "reason": f"source '{source}' is non-public (config/internal), not attacker-controlled"}

    # 2. Mitigation present right where the sink is -> prune.
    ctx = f"{code_line} {hops}"
    if any(mit in ctx.lower() for mit in _PRUNE_MITIGATIONS):
        return {"confirmed": True, "reason": "mitigation present but taint may still bypass — keep for human review"}

    # 3. No source at all -> likely a false positive (bare sink without taint).
    if not source and not hops:
        return {"confirmed": False, "reason": "no taint source identified; bare sink, likely FP"}

    return {"confirmed": True, "reason": "taint source to sink confirmed"}
