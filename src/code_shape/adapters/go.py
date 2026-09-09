#!/usr/bin/env python
"""go.py — Go language adapter."""
import re
from .base import LanguageAdapter


class GoAdapter(LanguageAdapter):
    name = "go"
    def_pattern = r"func\s+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\brange\b"]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bswitch\b"]
    write_patterns = [r"fmt\.Print"]
    read_patterns = [r"\bScan", r"\bReadFile"]

    def detect(self, code):
        return "package " in code or "func " in code or "fmt.Println" in code or ":=" in code

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*func\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
