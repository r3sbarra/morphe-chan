#!/usr/bin/env python
"""cpp.py — C++ language adapter (extends C)."""
from .c import CAdapter


class CppAdapter(CAdapter):
    name = "cpp"

    def detect(self, code):
        return "#include" in code or "std::" in code or "cout" in code or "vector" in code
