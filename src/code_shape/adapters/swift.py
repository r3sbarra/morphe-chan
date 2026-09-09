#!/usr/bin/env python
"""swift.py — Swift language adapter."""
import re
from .base import LanguageAdapter


class SwiftAdapter(LanguageAdapter):
    name = "swift"
    def_pattern = r"func\s+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\.forEach\("]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bswitch\b"]
    write_patterns = [r"\bprint\("]
    read_patterns = [r"\breadLine", r"\bread\("]

    def detect(self, code):
        return "func " in code or "print(" in code or "import Foundation" in code

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*func\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
