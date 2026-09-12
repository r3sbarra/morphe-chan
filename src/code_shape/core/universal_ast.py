#!/usr/bin/env python
"""universal_ast.py — Universal AST and structural dataflow parser for all popular languages.

Provides AST-level structural parsing, function boundary extraction, variable
dataflow tracking, call graph construction, and loop/branch complexity analysis
for all 13 supported languages:
  - Python
  - JavaScript & TypeScript
  - Java
  - C & C++
  - C#
  - Go
  - Rust
  - Ruby
  - PHP
  - Swift
  - Kotlin

Strictly standard library only (re, dataclasses, typing, collections).
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# Non-call keywords across languages to exclude from function calls
KEYWORD_CALLS = {
    "if", "for", "while", "do", "switch", "case", "catch", "return", "sizeof",
    "typeof", "instanceof", "new", "delete", "throw", "import", "export",
    "package", "class", "struct", "interface", "enum", "type", "func", "def",
    "function", "fn", "fun", "let", "const", "var", "mut", "auto",
    "public", "private", "protected", "static", "void", "int", "char", "bool",
    "string", "float", "double", "long", "short", "signed", "unsigned",
    "require", "include", "echo", "print", "println", "fmt", "console",
    "System", "select", "where", "from", "match", "when", "guard", "yield",
}

# Reserved keywords that cannot be variable names
RESERVED_VAR_NAMES = {
    "if", "else", "elif", "for", "while", "do", "switch", "case", "default",
    "return", "throw", "break", "continue", "goto", "class", "interface",
    "struct", "enum", "package", "import", "export", "true", "false", "null",
    "nil", "None", "undefined", "void", "public", "private", "protected",
    "static", "final", "const", "let", "var", "func", "def", "function", "fn"
}

# Control flow keywords for complexity analysis
BRANCH_KEYWORDS = {
    "if", "else", "switch", "case", "match", "when", "catch", "guard", "except"
}
LOOP_KEYWORDS = {
    "for", "while", "loop", "range", "foreach", "forEach"
}


@dataclass
class UniversalParam:
    name: str
    type_hint: Optional[str] = None


@dataclass
class UniversalFunction:
    """Structural AST node for a function or method in any language."""
    name: str
    receiver: Optional[str] = None
    params: List[UniversalParam] = field(default_factory=list)
    return_type: Optional[str] = None
    start_line: int = 1
    end_line: int = 1
    full_code: str = ""
    body: str = ""
    body_start_line: int = 1
    is_async: bool = False
    language: str = "generic"


def _strip_comments_and_strings(code: str) -> str:
    """Remove comments and replace string literals with empty quotes, preserving line counts."""
    out = []
    i = 0
    n = len(code)
    in_single_line_comment = False
    in_multi_line_comment = False
    comment_type = ""  # "//", "/*", "#"
    in_string = False
    string_quote = ""

    while i < n:
        c = code[i]
        next_c = code[i + 1] if i + 1 < n else ""

        if in_single_line_comment:
            if c == "\n":
                in_single_line_comment = False
                out.append("\n")
            else:
                out.append(" ")
            i += 1
            continue

        if in_multi_line_comment:
            if c == "*" and next_c == "/":
                in_multi_line_comment = False
                out.append("  ")
                i += 2
            elif c == "\n":
                out.append("\n")
            else:
                out.append(" ")
                i += 1
            continue

        if in_string:
            if c == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
            elif c == string_quote:
                in_string = False
                out.append(string_quote)
                i += 1
            elif c == "\n":
                out.append("\n")
                i += 1
            else:
                out.append(" ")
                i += 1
            continue

        # Check for comments
        if c == "/" and next_c == "/":
            in_single_line_comment = True
            comment_type = "//"
            out.append("  ")
            i += 2
            continue
        if c == "/" and next_c == "*":
            in_multi_line_comment = True
            comment_type = "/*"
            out.append("  ")
            i += 2
            continue
        if c == "#":
            in_single_line_comment = True
            comment_type = "#"
            out.append(" ")
            i += 1
            continue

        # Check for string literals
        if c in ('"', "'", "`"):
            in_string = True
            string_quote = c
            out.append(c)
            i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def _find_matching_brace(code: str, open_brace_idx: int) -> int:
    """Find the index of the matching closing brace '}' for the '{' at open_brace_idx.

    Handles nested braces while skipping strings and comments.
    """
    n = len(code)
    depth = 0
    i = open_brace_idx
    in_string = False
    string_quote = ""
    in_line_comment = False
    in_block_comment = False

    while i < n:
        c = code[i]
        next_c = code[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if c == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if c == "*" and next_c == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            if c == "\\" and i + 1 < n:
                i += 2
            elif c == string_quote:
                in_string = False
                i += 1
            else:
                i += 1
            continue

        if c == "/" and next_c == "/":
            in_line_comment = True
            i += 2
            continue
        if c == "/" and next_c == "*":
            in_block_comment = True
            i += 2
            continue
        if c == "#":
            in_line_comment = True
            i += 1
            continue
        if c in ('"', "'", "`"):
            in_string = True
            string_quote = c
            i += 1
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i

        i += 1
    return n - 1


def _find_matching_ruby_end(code: str, start_idx: int) -> int:
    """Find matching 'end' keyword for a Ruby def block."""
    lines = code[start_idx:].splitlines(keepends=True)
    depth = 0
    curr_offset = start_idx
    block_start_re = re.compile(r"^\s*(?:def|class|module|if|unless|while|until|for|case)\b|\bdo\s*(?:\|[^|]*\|)?\s*$")
    end_re = re.compile(r"^\s*end\b")

    for idx, line in enumerate(lines):
        clean = line.split("#")[0].strip()
        if not clean:
            curr_offset += len(line)
            continue
        if block_start_re.search(clean):
            depth += 1
        elif end_re.search(clean):
            depth -= 1
            if depth == 0:
                return curr_offset + len(line) - 1
        curr_offset += len(line)
    return len(code) - 1


def _parse_params(params_raw: str, lang: str) -> List[UniversalParam]:
    """Extract clean parameter names and optional type hints from parameter string."""
    params: List[UniversalParam] = []
    if not params_raw.strip():
        return params

    # Split by comma taking care not to split inside generic types <...> or nested tuples (...)
    parts: List[str] = []
    cur = []
    angle_depth = 0
    paren_depth = 0
    bracket_depth = 0
    for ch in params_raw:
        if ch == "<":
            angle_depth += 1
        elif ch == ">":
            angle_depth = max(0, angle_depth - 1)
        elif ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
        elif ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif ch == "," and angle_depth == 0 and paren_depth == 0 and bracket_depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())

    for part in parts:
        p = part.strip()
        if not p or p in ("...", "*", "**"):
            continue
        # Strip default value: x = val
        if "=" in p:
            p = p.split("=")[0].strip()

        # TypeScript / Python / Kotlin / Swift: name: Type
        if ":" in p:
            name_part, type_part = p.split(":", 1)
            name = name_part.strip().lstrip("$*&")
            # In Swift, param could be "label name: Type"
            if " " in name:
                name = name.split()[-1]
            if name and re.match(r"^[a-zA-Z_]\w*$", name):
                params.append(UniversalParam(name=name, type_hint=type_part.strip()))
                continue

        # Go: name Type or name *Type
        if lang in ("go", "golang") and " " in p:
            tokens = p.split()
            name = tokens[0].lstrip("$*&")
            type_hint = " ".join(tokens[1:])
            if name and re.match(r"^[a-zA-Z_]\w*$", name):
                params.append(UniversalParam(name=name, type_hint=type_hint))
                continue

        # C / C++ / Java / C#: Type name
        if lang in ("c", "cpp", "csharp", "cs", "java") and " " in p:
            tokens = p.split()
            name = tokens[-1].lstrip("$*&")
            type_hint = " ".join(tokens[:-1])
            if name and re.match(r"^[a-zA-Z_]\w*$", name):
                params.append(UniversalParam(name=name, type_hint=type_hint))
                continue

        # PHP: [Type] $name
        if "$" in p:
            tokens = p.split()
            for t in tokens:
                if t.startswith("$"):
                    name = t.lstrip("$")
                    type_hint = tokens[0] if tokens[0] != t else None
                    if name and re.match(r"^[a-zA-Z_]\w*$", name):
                        params.append(UniversalParam(name=name, type_hint=type_hint))
                        break
            continue

        # Fallback bare identifier
        name = p.strip().lstrip("$*&")
        if name and re.match(r"^[a-zA-Z_]\w*$", name):
            params.append(UniversalParam(name=name))

    return params


def extract_universal_functions(code: str, lang: str = "generic") -> List[UniversalFunction]:
    """Extract all functions/methods with accurate boundaries and signatures for any language."""
    funcs: List[UniversalFunction] = []
    lang = (lang or "generic").lower()
    total_len = len(code)
    if total_len == 0:
        return funcs

    # Calculate line starts for line number conversions
    line_offsets = [0]
    for idx, char in enumerate(code):
        if char == "\n":
            line_offsets.append(idx + 1)

    def offset_to_line(offset: int) -> int:
        import bisect
        return bisect.bisect_right(line_offsets, offset)

    # 1. Python handler
    if lang in ("python", "py"):
        import ast
        try:
            tree = ast.parse(code)
            lines = code.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = node.lineno
                    end = getattr(node, "end_lineno", None)
                    if end is None:
                        end = start
                    fn_code = "\n".join(lines[start - 1 : end])
                    body_start_line = node.body[0].lineno if node.body else start
                    inner_body = "\n".join(lines[body_start_line - 1 : end])
                    params = [
                        UniversalParam(
                            name=a.arg,
                            type_hint=ast.unparse(a.annotation) if a.annotation else None,
                        )
                        for a in node.args.args
                    ]
                    funcs.append(
                        UniversalFunction(
                            name=node.name,
                            params=params,
                            start_line=start,
                            end_line=end,
                            full_code=fn_code,
                            body=inner_body,
                            body_start_line=body_start_line,
                            is_async=isinstance(node, ast.AsyncFunctionDef),
                            language="python",
                        )
                    )
            if funcs:
                return funcs
        except Exception:
            pass  # fallback to regex scanner below

    # 2. Ruby handler
    if lang in ("ruby", "rb"):
        ruby_pattern = re.compile(r"^[ \t]*def\s+(?:self\.)?([a-zA-Z_]\w*[\?!]?)(?:[ \t]*\(([^)]*)\)|[ \t]+([^\n;]+))?", re.MULTILINE)
        for m in ruby_pattern.finditer(code):
            name = m.group(1)
            raw_params = m.group(2) or m.group(3) or ""
            start_offset = m.start()
            start_line = offset_to_line(start_offset)
            end_offset = _find_matching_ruby_end(code, start_offset)
            end_line = offset_to_line(end_offset)
            def_newline = code.find("\n", start_offset)
            body_start = (def_newline + 1) if def_newline != -1 else start_offset
            inner_body = code[body_start:end_offset]
            body_start_line = offset_to_line(body_start)
            fn_code = code[start_offset:end_offset + 1]
            funcs.append(
                UniversalFunction(
                    name=name,
                    params=_parse_params(raw_params, "ruby"),
                    start_line=start_line,
                    end_line=end_line,
                    full_code=fn_code,
                    body=inner_body,
                    body_start_line=body_start_line,
                    language="ruby",
                )
            )
        return funcs

    # 3. Curly-brace languages
    # Language-specific header patterns
    patterns: List[Tuple[str, re.Pattern]] = []

    if lang in ("javascript", "typescript", "js", "ts", "generic"):
        # standard function
        patterns.append((
            "js_fn",
            re.compile(r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function(?:\s+([a-zA-Z_]\w*))?\s*\(([^)]*)\)\s*(?::\s*[^{]+)?\{")
        ))
        # arrow functions: const foo = async (a, b) => {
        patterns.append((
            "js_arrow",
            re.compile(r"(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?(?:\(([^)]*)\)|([a-zA-Z_]\w*))\s*(?::\s*[^=]+)?=>\s*\{")
        ))
        # function assignment: const foo = function(a, b) {
        patterns.append((
            "js_assign_fn",
            re.compile(r"(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s+)?function\s*\(([^)]*)\)\s*\{")
        ))
        # class method / object method: foo(a, b) {
        patterns.append((
            "js_method",
            re.compile(r"^[ \t]*(?:public|private|protected|static|async|\*)*[ \t]*([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*(?::\s*[^{]+)?\{", re.MULTILINE)
        ))

    if lang in ("go", "golang"):
        # func (r *Recv) Name(params) (ret) { OR func Name(params) ret {
        patterns.append((
            "go_func",
            re.compile(r"func\s+(?:\((?:[a-zA-Z_]\w*\s+)?\*?([a-zA-Z_]\w*)\)\s+)?([a-zA-Z_]\w*)\s*\(([^)]*)\)[^{]*\{")
        ))

    if lang in ("rust", "rs"):
        # pub async fn name<T>(params) -> Ret {
        patterns.append((
            "rust_fn",
            re.compile(r"(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([a-zA-Z_]\w*)(?:<[^>]*>)?\s*\(([^)]*)\)[^{]*\{")
        ))

    if lang in ("java", "csharp", "cs"):
        # [modifiers] ReturnType Name<T>(params) throws ... {
        patterns.append((
            "java_cs_method",
            re.compile(r"(?:(?:public|private|protected|internal|static|final|abstract|synchronized|override|virtual|async)\s+)*([\w<>\[\]\?]+)\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)[^{]*\{")
        ))

    if lang in ("c", "cpp", "c++"):
        # void Class::Name(params) const {
        patterns.append((
            "c_cpp_func",
            re.compile(r"(?:(?:inline|static|virtual|explicit|extern|const)\s+)*(?:[\w:*&<>\[\]]+)\s+(?:(?:\w+::)?([a-zA-Z_]\w*))\s*\(([^)]*)\)\s*(?:const)?\s*\{")
        ))

    if lang in ("php",):
        # function name(params) {
        patterns.append((
            "php_func",
            re.compile(r"(?:(?:public|private|protected|static)\s+)*function\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)[^{]*\{")
        ))

    if lang in ("swift",):
        # func name(params) -> Ret {
        patterns.append((
            "swift_func",
            re.compile(r"(?:(?:public|private|fileprivate|internal|open|static|override|mutating)\s+)*func\s+([a-zA-Z_]\w*)(?:<[^>]*>)?\s*\(([^)]*)\)[^{]*\{")
        ))

    if lang in ("kotlin", "kt"):
        # fun name(params): Ret {
        patterns.append((
            "kotlin_func",
            re.compile(r"(?:(?:public|private|protected|internal|override|suspend|inline)\s+)*fun\s+(?:<[^>]*>\s+)?([a-zA-Z_]\w*)\s*\(([^)]*)\)[^{]*\{")
        ))

    # Fallback generic pattern if no specific matches
    patterns.append((
        "generic_func",
        re.compile(r"(?:def|function|func|fn|fun)\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)[^{]*\{")
    ))

    seen_spans: Set[Tuple[int, int]] = set()

    for kind, pat in patterns:
        for m in pat.finditer(code):
            start_offset = m.start()
            open_brace_idx = code.find("{", m.start())
            if open_brace_idx == -1:
                continue
            end_brace_idx = _find_matching_brace(code, open_brace_idx)

            # Check if this function span was already captured
            span_key = (start_offset, end_brace_idx)
            if any(s <= start_offset and end_brace_idx <= e for s, e in seen_spans):
                continue

            # Extract function name, receiver, and params based on regex kind
            receiver = None
            if kind == "go_func":
                receiver = m.group(1)
                name = m.group(2)
                raw_params = m.group(3)
            elif kind == "java_cs_method":
                name = m.group(2)
                raw_params = m.group(3)
            elif kind == "js_arrow":
                name = m.group(1)
                raw_params = m.group(2) or m.group(3) or ""
            else:
                name = m.group(1)
                raw_params = m.group(2) if len(m.groups()) >= 2 else ""

            if not name or name in KEYWORD_CALLS:
                continue

            seen_spans.add(span_key)
            start_line = offset_to_line(start_offset)
            end_line = offset_to_line(end_brace_idx)
            full_fn_code = code[start_offset:end_brace_idx + 1]
            inner_body = code[open_brace_idx + 1:end_brace_idx]
            body_start_line = offset_to_line(open_brace_idx + 1)

            params = _parse_params(raw_params, lang)
            funcs.append(
                UniversalFunction(
                    name=name,
                    receiver=receiver,
                    params=params,
                    start_line=start_line,
                    end_line=end_line,
                    full_code=full_fn_code,
                    body=inner_body,
                    body_start_line=body_start_line,
                    language=lang,
                )
            )

    # Sort functions by appearance in file
    funcs.sort(key=lambda f: f.start_line)
    return funcs


def _extract_identifiers(expr: str) -> Set[str]:
    """Extract variable and identifier names from an expression, excluding keywords/numbers/literals."""
    # Strip string literals so letters/words inside quotes aren't treated as identifiers
    clean = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', expr)
    clean = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", clean)
    clean = re.sub(r'`[^`\\]*(?:\\.[^`\\]*)*`', '``', clean)
    tokens = re.findall(r"\b([a-zA-Z_]\w*)\b", clean)
    return {t for t in tokens if t not in KEYWORD_CALLS and not t.isdigit()}


def parse_function_dataflow(fn: UniversalFunction, base_lineno: int = 1) -> Dict[str, Any]:
    """Parse intra-procedural dataflow for a function in any language.

    Returns:
      vars: Dict[str, VarNode]
      edges: List[DataEdge]
      calls: List[str]
      call_sites: List[Tuple[str, List[str]]]
      returns: List[str]
      statements: int
      branches: int
      loops: int
      complexity: str
    """
    from code_shape.core.dataflow import DataEdge, VarNode

    vars_dict: Dict[str, VarNode] = {}
    edges: List[DataEdge] = []
    calls: List[str] = []
    call_sites: List[Tuple[str, List[str]]] = []
    returns: List[str] = []
    branches = 0
    loops = 0
    statements = 0
    max_loop_depth = 0
    current_loop_depth = 0

    # Register parameters
    for p in fn.params:
        vars_dict[p.name] = VarNode(
            name=p.name,
            kind="param",
            defined_at=fn.start_line,
            type_hint=p.type_hint,
        )

    # Split body into lines
    lines = fn.body.splitlines()
    for idx, raw_line in enumerate(lines):
        line_no = fn.body_start_line + idx
        line = raw_line.strip()
        if not line or line.startswith(("//", "/*", "*", "#")):
            continue

        statements += 1

        # Complexity tracking: loops
        if any(re.search(r"\b" + re.escape(kw) + r"\b", line) for kw in LOOP_KEYWORDS):
            loops += 1
            current_loop_depth += 1
            if current_loop_depth > max_loop_depth:
                max_loop_depth = current_loop_depth

        # Complexity tracking: branches
        if any(re.search(r"\b" + re.escape(kw) + r"\b", line) for kw in BRANCH_KEYWORDS):
            branches += 1

        # Decrement loop depth on closing braces
        if "}" in line and current_loop_depth > 0:
            current_loop_depth = max(0, current_loop_depth - line.count("}"))

        # 1. Assignments
        # Go: dst := expr
        # JS/TS: const/let/var dst = expr
        # Rust: let (mut)? dst (= expr)?
        # Java/C/C#: Type dst = expr
        # PHP: $dst = expr
        # Python/Ruby: dst = expr
        assign_match = None
        # Go short declaration
        m_go = re.search(r"\b([a-zA-Z_]\w*)\s*:=\s*(.+)", line)
        # Var declaration: let/const/var/val dst = expr
        m_decl = re.search(r"\b(?:const|let|var|val)\s+(?:mut\s+)?([a-zA-Z_]\w*)(?:\s*:[^=]+)?\s*=\s*(.+)", line)
        # Typed declaration: Type dst = expr
        m_typed = re.search(r"^[ \t]*(?:[\w<>\[\]*&]+)\s+([a-zA-Z_]\w*)\s*=\s*(.+)", line)
        # PHP: $dst = expr
        m_php = re.search(r"\$([a-zA-Z_]\w*)\s*=\s*(.+)", line)
        # Simple assignment: dst = expr
        m_simple = re.search(r"\b([a-zA-Z_]\w*)\s*(=|\+=|-=|\*=|/=|%=)\s*([^=].*)", line)

        dst = None
        rhs = None
        op = "="

        if m_go:
            dst, rhs = m_go.group(1), m_go.group(2)
        elif m_decl:
            dst, rhs = m_decl.group(1), m_decl.group(2)
        elif m_php:
            dst, rhs = m_php.group(1), m_php.group(2)
        elif m_typed:
            dst, rhs = m_typed.group(1), m_typed.group(2)
        elif m_simple:
            dst, op, rhs = m_simple.group(1), m_simple.group(2), m_simple.group(3)

        if dst and dst not in RESERVED_VAR_NAMES and rhs:
            # Strip trailing semicolon
            rhs = rhs.rstrip(";").strip()
            srcs = _extract_identifiers(rhs)
            if op != "=":
                srcs.add(dst)

            if dst not in vars_dict:
                vars_dict[dst] = VarNode(name=dst, kind="local", defined_at=line_no)

            for s in srcs:
                if s != dst:
                    edges.append(DataEdge(src=s, dst=dst, line=line_no, kind="assign"))

        # 2. Function calls: callee(args...)
        for call_m in re.finditer(r"(?:([a-zA-Z_]\w*)\.)?([a-zA-Z_]\w*)\s*\(([^)]*)\)", line):
            obj, func_name, args_str = call_m.group(1), call_m.group(2), call_m.group(3)
            if func_name in KEYWORD_CALLS:
                continue

            full_callee = f"{obj}.{func_name}" if obj else func_name
            calls.append(full_callee)
            arg_names = [n for n in _extract_identifiers(args_str)]
            call_sites.append((full_callee, arg_names))

            for a_name in arg_names:
                edges.append(DataEdge(src=a_name, dst=f"call:{full_callee}", line=line_no, kind="call_arg"))

        # 3. Return statements: return expr
        ret_m = re.search(r"\breturn(?:\s+([^;]+))?", line)
        if ret_m:
            ret_expr = (ret_m.group(1) or "").strip()
            returns.append(ret_expr)
            for ret_var in _extract_identifiers(ret_expr):
                edges.append(DataEdge(src=ret_var, dst="return", line=line_no, kind="return"))

    # Estimate complexity class
    if max_loop_depth == 0:
        complexity = "O(1)"
    elif max_loop_depth == 1:
        complexity = "O(n)"
    elif max_loop_depth == 2:
        complexity = "O(n^2)"
    else:
        complexity = f"O(n^{max_loop_depth})"

    # Deduplicate edges and calls
    dedup_edges = []
    seen_edge = set()
    for e in edges:
        ekey = (e.src, e.dst, e.line, e.kind)
        if ekey not in seen_edge:
            seen_edge.add(ekey)
            dedup_edges.append(e)

    return {
        "vars": vars_dict,
        "edges": dedup_edges,
        "calls": list(dict.fromkeys(calls)),
        "call_sites": call_sites,
        "returns": returns,
        "statements": statements,
        "branches": branches,
        "loops": loops,
        "complexity": complexity,
    }


def parse_universal_dfg(code: str, lang: str = "generic") -> Any:
    """Build a complete ProjectDFG with real intra- and inter-procedural dataflow for any language."""
    from code_shape.core.dataflow import ProjectDFG, FunctionDFG

    proj = ProjectDFG()
    funcs = extract_universal_functions(code, lang)

    for fn in funcs:
        dfg = FunctionDFG(name=fn.name)
        dfg.params = [p.name for p in fn.params]
        dfg.line_range = (fn.start_line, fn.end_line)
        dfg.lines = max(1, fn.end_line - fn.start_line + 1)

        flow = parse_function_dataflow(fn)
        dfg.vars = flow["vars"]
        dfg.edges = flow["edges"]
        dfg.calls = flow["calls"]
        dfg.call_sites = flow["call_sites"]
        dfg.returns = flow["returns"]
        dfg.statements = flow["statements"]
        dfg.branches = flow["branches"]
        dfg.loops = flow["loops"]
        dfg.complexity = flow["complexity"]

        proj.functions[fn.name] = dfg

    # Populate call edges: caller -> callee
    for name, dfg in proj.functions.items():
        for callee in dfg.calls:
            callee_bare = callee.split(".")[-1]
            target = callee if callee in proj.functions else (callee_bare if callee_bare in proj.functions else None)
            if target:
                proj.call_edges.append((name, target))

    # Populate inter-procedural data edges: caller -> callee -> var
    for name, dfg in proj.functions.items():
        for callee, arg_names in dfg.call_sites:
            callee_bare = callee.split(".")[-1]
            target = callee if callee in proj.functions else (callee_bare if callee_bare in proj.functions else None)
            if target:
                callee_dfg = proj.functions[target]
                for i, arg in enumerate(arg_names):
                    if i < len(callee_dfg.params):
                        proj.data_edges.append((name, target, arg))

    proj.call_edges = list(dict.fromkeys(proj.call_edges))
    proj.data_edges = list(dict.fromkeys(proj.data_edges))
    return proj
