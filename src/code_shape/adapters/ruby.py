#!/usr/bin/env python
"""ruby.py — Ruby language adapter."""
import re
from .base import LanguageAdapter


class RubyAdapter(LanguageAdapter):
    name = "ruby"
    def_pattern = r"def\s+(\w+)"
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\.each\b", r"\bdo\b"]
    branch_patterns = [r"\bif\b", r"\belsif\b", r"\belse\b", r"\bcase\b"]
    write_patterns = [r"\bputs", r"\bprint"]
    read_patterns = [r"\bgets", r"\bFile\.read"]

    def detect(self, code):
        return "def " in code or "puts " in code or "require " in code or "do |" in code

    # Ruby implicitly returns the last evaluated expression in a def...end.
    # A def whose final non-blank body line is a bare expression (not
    # return/puts/print/assignment-only) is a tail-return method.
    tail_return_patterns = [
        r"def\s+\w+[^\n]*\n(?:(?![ \t]*end\b).*\n)*?[ \t]*(?![ \t]*(?:return|puts|print|raise)\b)\S+[^\n]*\n[ \t]*end\b",
    ]

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*def\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
