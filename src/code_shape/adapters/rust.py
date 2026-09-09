#!/usr/bin/env python
"""rust.py — Rust language adapter."""
import re
from .base import LanguageAdapter


class RustAdapter(LanguageAdapter):
    name = "rust"
    def_pattern = r"fn\s+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\bloop\b"]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bmatch\b"]
    write_patterns = [r"println!", r"\bprint!"]
    read_patterns = [r"\bread_line", r"\bread_to_string"]

    def detect(self, code):
        return "fn " in code or "let mut" in code or "println!" in code or "impl " in code

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*fn\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
