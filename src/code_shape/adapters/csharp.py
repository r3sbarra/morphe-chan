#!/usr/bin/env python
"""csharp.py — C# language adapter."""
import re
from .base import LanguageAdapter


class CSharpAdapter(LanguageAdapter):
    name = "csharp"
    def_pattern = r"(?:public|private|protected|static)?\s*(?:\w+\s+)*(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\bforeach\b", r"\bdo\b"]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bswitch\b"]
    write_patterns = [r"Console\.Write"]
    read_patterns = [r"Console\.ReadLine"]

    def detect(self, code):
        return "using System" in code or "Console.WriteLine" in code or "foreach" in code or "namespace" in code

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*(?:public|private|protected|static)", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
