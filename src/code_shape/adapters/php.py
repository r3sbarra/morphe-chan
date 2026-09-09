#!/usr/bin/env python
"""php.py — PHP language adapter."""
import re
from .base import LanguageAdapter


class PhpAdapter(LanguageAdapter):
    name = "php"
    def_pattern = r"(?:public|private|protected|static)?\s*function\s+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\bforeach\b"]
    branch_patterns = [r"\bif\b", r"\belseif\b", r"\belse\b", r"\bswitch\b"]
    write_patterns = [r"\becho", r"\bprint"]
    read_patterns = [r"\$_GET", r"\$_POST", r"\bfopen"]

    def detect(self, code):
        return "<?php" in code or "function " in code or "echo " in code or "$" in code

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*function\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
