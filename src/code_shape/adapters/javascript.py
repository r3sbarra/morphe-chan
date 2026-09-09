#!/usr/bin/env python
"""javascript.py — JavaScript language adapter."""
import re
from .base import LanguageAdapter


def _extract_braced(code: str, start: int) -> str:
    """Extract a balanced-brace block starting at `start` (the '{')."""
    depth = 0
    i = start
    while i < len(code):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return code[start:i + 1]
        i += 1
    return code[start:]


class JavaScriptAdapter(LanguageAdapter):
    name = "javascript"
    def_pattern = r"(?:function|const\s+\w+\s*=\s*\(|let\s+\w+\s*=\s*\()\s*(\w+)?\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\.forEach\(", r"\.map\("]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bswitch\b"]
    write_patterns = [r"console\.log", r"\bdocument\.write"]

    def detect(self, code):
        return "function " in code or "console.log" in code or "=>" in code

    def extract_functions(self, code):
        """Extract functions + arrow functions + module-export methods."""
        functions = super().extract_functions(code)
        # arrow functions: const foo = (a, b) => { ... }
        for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", code):
            name = m.group(1)
            if name not in functions:
                start = code.find("{", m.end())
                if start != -1:
                    body = _extract_braced(code, start)
                    functions[name] = f"function {name}(...){body}"
        # module.exports = { foo: () => {...} } and object methods
        for m in re.finditer(r"(\w+)\s*:\s*(?:async\s*)?\([^)]*\)\s*=>", code):
            name = m.group(1)
            if name not in functions:
                start = code.find("{", m.end())
                if start != -1:
                    body = _extract_braced(code, start)
                    functions[name] = f"function {name}(...){body}"
        return functions

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*(?:function|const|let|var)\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
