#!/usr/bin/env python
"""python.py — Python language adapter."""
import re
from .base import LanguageAdapter


class PythonAdapter(LanguageAdapter):
    name = "python"
    def_pattern = r"(?:def|async def)\s+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b"]
    branch_patterns = [r"\bif\b", r"\belif\b", r"\belse\b"]
    # READ: input, file read, web GET/request
    read_patterns = [r"\binput\(", r"\bopen\(", r"\bread\(", r"\breadline",
                     r"urlopen", r"requests\.get", r"requests\.post", r"\.get\(",
                     r"fetch\(", r"\bget\("]
    # WRITE: print, file write, web POST/send, output
    write_patterns = [r"\bprint\(", r"\.write\(", r"requests\.post", r"\.send\(",
                      r"\bwrite\(", r"\bemit", r"\boutput"]

    def detect(self, code):
        return "def " in code or "print(" in code or "import " in code

    def decompose(self, code):
        counts = super().decompose(code)
        # write-mode open(path, 'w'/'a') is WRITE, not READ
        write_opens = len(re.findall(r"open\s*\([^)]*['\"][wa]\b", code))
        counts["READ"] = max(0, counts["READ"] - write_opens)
        counts["WRITE"] = counts.get("WRITE", 0) + write_opens
        # SQL operations: SELECT = READ, INSERT/UPDATE/DELETE = WRITE
        sql_read = len(re.findall(r"execute\s*\([^)]*SELECT", code, re.IGNORECASE))
        sql_write = len(re.findall(r"execute\s*\([^)]*(?:INSERT|UPDATE|DELETE|CREATE|DROP)", code, re.IGNORECASE))
        counts["READ"] = counts.get("READ", 0) + sql_read
        counts["WRITE"] = counts.get("WRITE", 0) + sql_write
        return counts

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*(?:def|async def)\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]
