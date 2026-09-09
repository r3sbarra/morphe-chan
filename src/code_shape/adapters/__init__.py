"""adapters — Language adapter package.

Each language has its own adapter file mapping its syntax to the common
primitive vocabulary. Add a new language by creating a new file here and
registering it in ADAPTERS.
"""
from .base import LanguageAdapter, PRIMITIVES
from .python import PythonAdapter
from .javascript import JavaScriptAdapter
from .typescript import TypeScriptAdapter
from .java import JavaAdapter
from .c import CAdapter
from .cpp import CppAdapter
from .csharp import CSharpAdapter
from .go import GoAdapter
from .rust import RustAdapter
from .ruby import RubyAdapter
from .php import PhpAdapter
from .swift import SwiftAdapter
from .kotlin import KotlinAdapter

# All registered adapters (order matters for detection preference).
ADAPTERS = [
    PythonAdapter(), JavaScriptAdapter(), TypeScriptAdapter(), JavaAdapter(),
    CAdapter(), CppAdapter(), CSharpAdapter(), GoAdapter(), RustAdapter(),
    RubyAdapter(), PhpAdapter(), SwiftAdapter(), KotlinAdapter(),
]

__all__ = ["LanguageAdapter", "PRIMITIVES", "ADAPTERS"]
