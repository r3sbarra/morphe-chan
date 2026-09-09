#!/usr/bin/env python
"""typescript.py — TypeScript language adapter (extends JavaScript)."""
from .javascript import JavaScriptAdapter


class TypeScriptAdapter(JavaScriptAdapter):
    name = "typescript"

    def detect(self, code):
        return (": string" in code or ": number" in code or "interface " in code
                or "type " in code or "number[]" in code)
