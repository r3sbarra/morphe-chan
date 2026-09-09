#!/usr/bin/env python
"""java.py — Java language adapter."""
import re
from .base import LanguageAdapter


class JavaAdapter(LanguageAdapter):
    name = "java"
    def_pattern = r"(?:public|private|protected|static)?\s*(?:\w+\s+)*(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\.forEach\("]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bswitch\b"]
    write_patterns = [r"System\.out\.print"]
    read_patterns = [r"Scanner", r"\breadLine", r"\bnextInt"]

    def detect(self, code):
        return "public " in code or "class " in code or "System.out" in code or "int[]" in code

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*(?:public|private|protected|static)", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
