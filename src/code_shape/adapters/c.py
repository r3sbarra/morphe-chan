#!/usr/bin/env python
"""c.py — C language adapter."""
import re
from .base import LanguageAdapter


class CAdapter(LanguageAdapter):
    name = "c"
    def_pattern = r"(?:\w+\s+)+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\bdo\b"]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bswitch\b"]
    write_patterns = [r"\bprintf"]
    read_patterns = [r"\bscanf", r"\bfread", r"\bgetchar"]

    def detect(self, code):
        return "#include" in code or "printf(" in code or "int main" in code or "malloc" in code

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*(?:\w+\s+)+(\w+)\s*\(", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
