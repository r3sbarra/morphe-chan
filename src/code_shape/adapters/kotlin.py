#!/usr/bin/env python
"""kotlin.py — Kotlin language adapter."""
import re
from .base import LanguageAdapter


class KotlinAdapter(LanguageAdapter):
    name = "kotlin"
    def_pattern = r"fun\s+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\.forEach\("]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bwhen\b"]
    write_patterns = [r"\bprintln"]
    read_patterns = [r"\breadLine", r"\breadln"]

    def detect(self, code):
        return "fun " in code or "println(" in code or "val " in code or "package " in code

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*fun\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
