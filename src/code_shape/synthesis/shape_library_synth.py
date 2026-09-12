#!/usr/bin/env python
"""shape_library_synth.py — Code synthesis via shape + library knowledge (v2).

v2 fixes:
  - consistent param naming (the param name is used in the library call)
  - clean templates (no duplicate library calls)
  - correct module prefixes (BeautifulSoup, not bs4.BeautifulSoup)

Uses:
  1. LIBRARY SHAPES — pick the right library call for the intent
  2. SHAPE — the target primitive structure
  3. TRANSFORM — the processing (parse/escape)

Dependency-free (stdlib only).
"""
from typing import Dict, Optional

from code_shape.analysis.algorithm_detector import detect_algorithm

# ── Algorithm templates (for complex algorithms detected from shape) ────────
ALGORITHM_TEMPLATES = {
    "binary_search": {
        "python": "def {name}(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
        "javascript": "function {name}(arr, target) {{\n    let low = 0, high = arr.length - 1;\n    while (low <= high) {{\n        const mid = Math.floor((low + high) / 2);\n        if (arr[mid] === target) return mid;\n        else if (arr[mid] < target) low = mid + 1;\n        else high = mid - 1;\n    }}\n    return -1;\n}}",
        "go": "func {name}(arr []int, target int) int {{\n    low, high := 0, len(arr)-1\n    for low <= high {{\n        mid := (low + high) / 2\n        if arr[mid] == target {{\n            return mid\n        }} else if arr[mid] < target {{\n            low = mid + 1\n        }} else {{\n            high = mid - 1\n        }}\n    }}\n    return -1\n}}",
    },
    "linear_search": {
        "python": "def {name}(arr, target):\n    for i in range(len(arr)):\n        if arr[i] == target:\n            return i\n    return -1",
        "javascript": "function {name}(arr, target) {{\n    for (let i = 0; i < arr.length; i++) {{\n        if (arr[i] === target) return i;\n    }}\n    return -1;\n}}",
        "go": "func {name}(arr []int, target int) int {{\n    for i, v := range arr {{\n        if v == target {{\n            return i\n        }}\n    }}\n    return -1\n}}",
    },
    "bubble_sort": {
        "python": "def {name}(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n - i - 1):\n            if arr[j] > arr[j + 1]:\n                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n    return arr",
        "javascript": "function {name}(arr) {{\n    const n = arr.length;\n    for (let i = 0; i < n; i++) {{\n        for (let j = 0; j < n - i - 1; j++) {{\n            if (arr[j] > arr[j + 1]) {{\n                [arr[j], arr[j + 1]] = [arr[j + 1], arr[j]];\n            }}\n        }}\n    }}\n    return arr;\n}}",
        "go": "func {name}(arr []int) []int {{\n    n := len(arr)\n    for i := 0; i < n; i++ {{\n        for j := 0; j < n-i-1; j++ {{\n            if arr[j] > arr[j+1] {{\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n            }}\n        }}\n    }}\n    return arr\n}}",
    },
    "merge_sort": {
        "python": "def {name}(arr):\n    if len(arr) <= 1:\n        return arr\n    mid = len(arr) // 2\n    left = {name}(arr[:mid])\n    right = {name}(arr[mid:])\n    return merge(left, right)",
        "javascript": "function {name}(arr) {{\n    if (arr.length <= 1) return arr;\n    const mid = Math.floor(arr.length / 2);\n    const left = {name}(arr.slice(0, mid));\n    const right = {name}(arr.slice(mid));\n    return merge(left, right);\n}}",
    },
    "quick_sort": {
        "python": "def {name}(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return {name}(left) + middle + {name}(right)",
        "javascript": "function {name}(arr) {{\n    if (arr.length <= 1) return arr;\n    const pivot = arr[Math.floor(arr.length / 2)];\n    const left = arr.filter(x => x < pivot);\n    const middle = arr.filter(x => x === pivot);\n    const right = arr.filter(x => x > pivot);\n    return [...{name}(left), ...middle, ...{name}(right)];\n}}",
    },
    "fibonacci": {
        "python": "def {name}(n):\n    if n <= 1:\n        return n\n    return {name}(n - 1) + {name}(n - 2)",
        "javascript": "function {name}(n) {{\n    if (n <= 1) return n;\n    return {name}(n - 1) + {name}(n - 2);\n}}",
        "go": "func {name}(n int) int {{\n    if n <= 1 {{\n        return n\n    }}\n    return {name}(n-1) + {name}(n-2)\n}}",
    },
    "factorial": {
        "python": "def {name}(n):\n    if n <= 1:\n        return 1\n    return n * {name}(n - 1)",
        "javascript": "function {name}(n) {{\n    if (n <= 1) return 1;\n    return n * {name}(n - 1);\n}}",
        "go": "func {name}(n int) int {{\n    if n <= 1 {{\n        return 1\n    }}\n    return n * {name}(n-1)\n}}",
    },
    "two_sum": {
        "python": "def {name}(nums, target):\n    seen = {{}}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []",
        "javascript": "function {name}(nums, target) {{\n    const seen = new Map();\n    for (let i = 0; i < nums.length; i++) {{\n        const diff = target - nums[i];\n        if (seen.has(diff)) return [seen.get(diff), i];\n        seen.set(nums[i], i);\n    }}\n    return [];\n}}",
        "go": "func {name}(nums []int, target int) []int {{\n    seen := make(map[int]int)\n    for i, num := range nums {{\n        diff := target - num\n        if idx, ok := seen[diff]; ok {{\n            return []int{{idx, i}}\n        }}\n        seen[num] = i\n    }}\n    return nil\n}}",
    },
}


def synthesize_algorithm(algorithm: str, lang: str = "python", name: str = "fn") -> Optional[str]:
    """Synthesize an algorithm from its detected name."""
    tpl = ALGORITHM_TEMPLATES.get(algorithm, {}).get(lang)
    if not tpl:
        return None
    return tpl.format(name=name)


# ── Class templates (for design patterns) ───────────────────────────────────
CLASS_TEMPLATES = {
    "singleton": {
        "python": "class {name}:\n    _instance = None\n    def __new__(cls):\n        if cls._instance is None:\n            cls._instance = super().__new__(cls)\n        return cls._instance\n    def __init__(self):\n        pass",
        "javascript": "class {name} {{\n    constructor() {{\n        if ({name}._instance) {{\n            return {name}._instance;\n        }}\n        {name}._instance = this;\n    }}\n}}",
    },
    "factory": {
        "python": "class {name}:\n    def create(self, type):\n        if type == 'a':\n            return TypeA()\n        elif type == 'b':\n            return TypeB()\n        raise ValueError('unknown type')",
        "javascript": "class {name} {{\n    create(type) {{\n        if (type === 'a') return new TypeA();\n        if (type === 'b') return new TypeB();\n        throw new Error('unknown type');\n    }}\n}}",
    },
    "observer": {
        "python": "class {name}:\n    def __init__(self):\n        self._observers = []\n    def attach(self, observer):\n        self._observers.append(observer)\n    def notify(self, event):\n        for obs in self._observers:\n            obs.update(event)",
        "javascript": "class {name} {{\n    constructor() {{\n        this.observers = [];\n    }}\n    attach(observer) {{\n        this.observers.push(observer);\n    }}\n    notify(event) {{\n        for (const obs of this.observers) obs.update(event);\n    }}\n}}",
    },
    "stack": {
        "python": "class {name}:\n    def __init__(self):\n        self._items = []\n    def push(self, item):\n        self._items.append(item)\n    def pop(self):\n        return self._items.pop()\n    def is_empty(self):\n        return len(self._items) == 0",
        "javascript": "class {name} {{\n    constructor() {{\n        this.items = [];\n    }}\n    push(item) {{\n        this.items.push(item);\n    }}\n    pop() {{\n        return this.items.pop();\n    }}\n    isEmpty() {{\n        return this.items.length === 0;\n    }}\n}}",
        "go": "type {name} struct {{\n    items []interface{{}}\n}}\n\nfunc (s *{name}) Push(item interface{{}}) {{\n    s.items = append(s.items, item)\n}}\n\nfunc (s *{name}) Pop() interface{{}} {{\n    if len(s.items) == 0 {{\n        return nil\n    }}\n    item := s.items[len(s.items)-1]\n    s.items = s.items[:len(s.items)-1]\n    return item\n}}\n\nfunc (s *{name}) IsEmpty() bool {{\n    return len(s.items) == 0\n}}",
    },
    "queue": {
        "python": "class {name}:\n    def __init__(self):\n        self._items = []\n    def enqueue(self, item):\n        self._items.append(item)\n    def dequeue(self):\n        return self._items.pop(0)\n    def is_empty(self):\n        return len(self._items) == 0",
        "javascript": "class {name} {{\n    constructor() {{\n        this.items = [];\n    }}\n    enqueue(item) {{\n        this.items.push(item);\n    }}\n    dequeue() {{\n        return this.items.shift();\n    }}\n    isEmpty() {{\n        return this.items.length === 0;\n    }}\n}}",
        "go": "type {name} struct {{\n    items []interface{{}}\n}}\n\nfunc (q *{name}) Enqueue(item interface{{}}) {{\n    q.items = append(q.items, item)\n}}\n\nfunc (q *{name}) Dequeue() interface{{}} {{\n    if len(q.items) == 0 {{\n        return nil\n    }}\n    item := q.items[0]\n    q.items = q.items[1:]\n    return item\n}}\n\nfunc (q *{name}) IsEmpty() bool {{\n    return len(q.items) == 0\n}}",
    },
}


def synthesize_class(pattern: str, lang: str = "python", name: str = "MyClass") -> Optional[str]:
    """Synthesize a class from its detected design pattern."""
    tpl = CLASS_TEMPLATES.get(pattern, {}).get(lang)
    if not tpl:
        return None
    return tpl.format(name=name)


def list_synthesis_intents() -> Dict:
    """Return all available synthesis intents, shapes, algorithms, and patterns with their supported languages."""
    return {
        "library_intents": {intent: list(tpls.keys()) for intent, tpls in LIBRARY_TEMPLATES.items()},
        "algorithm_intents": {alg: list(tpls.keys()) for alg, tpls in ALGORITHM_TEMPLATES.items()},
        "class_patterns": {pat: list(tpls.keys()) for pat, tpls in CLASS_TEMPLATES.items()},
        "shapes": {s: list(tpls.keys()) for s, tpls in SHAPE_TEMPLATES.items()},
    }

# ── Library call templates per intent ───────────────────────────────────────
# Each intent: {lang: (module, call, args_template, role)}
# args_template uses {param} for the function parameter.
LIBRARY_TEMPLATES = {
    "fetch_api": {
        "python": ("requests", "get", "f'https://api.example.com/{param}'", "NETWORK"),
        "javascript": ("fetch", "", "`https://api.example.com/${param}`", "NETWORK"),
        "go": ("http", "Get", '"https://api.example.com/" + param', "NETWORK"),
    },
    "scrape_web": {
        "python": ("BeautifulSoup", "", "resp.text, 'html.parser'", "SCRAPE"),
        "javascript": ("cheerio", "load", "resp.data", "SCRAPE"),
    },
    "query_db": {
        "python": ("db", "execute", "'SELECT * FROM t WHERE id = ?', ({param},)", "SQL"),
        "javascript": ("db", "query", "'SELECT * FROM t WHERE id = ?', [{param}]", "SQL"),
        "go": ("db", "Query", "'SELECT * FROM t WHERE id = ?', param", "SQL"),
    },
    "read_file": {
        "python": ("open", "", "{param}, 'r'", "FILE"),
        "javascript": ("fs", "readFileSync", "{param}, 'utf8'", "FILE"),
        "go": ("os", "ReadFile", "param", "FILE"),
    },
    "render_html": {
        "python": ("flask", "render_template", "'page.html', data={param}", "RENDER"),
        "javascript": ("res", "send", "data", "RENDER"),
    },
    "exec_cmd": {
        "python": ("subprocess", "run", "[{param}], capture_output=True", "EXEC"),
        "javascript": ("cp", "execSync", "{param}", "EXEC"),
        "go": ("exec", "Command", "param", "EXEC"),
    },
    "write_file": {
        "python": ("open", "", "{param}, 'w'", "FILE"),
        "javascript": ("fs", "writeFileSync", "{param}, data", "FILE"),
    },
    "send_email": {
        "python": ("smtplib", "sendmail", "from_addr, to_addr, msg", "NETWORK"),
    },
    "parse_json": {
        "python": ("json", "loads", "data", "SAFE"),
        "javascript": ("JSON", "parse", "data", "SAFE"),
    },
    "hash_password": {
        "python": ("bcrypt", "hashpw", "pw.encode(), bcrypt.gensalt()", "CRYPTO_SAFE"),
        "javascript": ("bcrypt", "hash", "pw, 10", "CRYPTO_SAFE"),
    },
}

# ── Transform templates per intent (the processing after the fetch) ────────
TRANSFORM_TEMPLATES = {
    "fetch_api": {"python": "result = json.loads(resp.text)",
                  "javascript": "const result = JSON.parse(resp.data);"},
    "scrape_web": {"python": "soup = BeautifulSoup(resp.text, 'html.parser')\n    result = soup.find('title').text",
                   "javascript": "const $ = cheerio.load(resp.data);\n    const result = $('title').text();"},
    "query_db": {"python": "result = db.execute('SELECT * FROM t WHERE id = ?', ({param},)).fetchall()",
                 "javascript": "const result = await db.query('SELECT * FROM t WHERE id = ?', [{param}]);"},
    "read_file": {"python": "result = open({param}, 'r').read()",
                  "javascript": "const result = fs.readFileSync({param}, 'utf8');"},
    "exec_cmd": {"python": "result = subprocess.run([{param}], capture_output=True)",
                 "javascript": "const result = cp.execSync({param});"},
    "hash_password": {"python": "result = bcrypt.hashpw({param}.encode(), bcrypt.gensalt())",
                       "javascript": "const result = bcrypt.hash({param}, 10);"},
}

# ── Shape templates (the primitive structure) ──────────────────────────────
SHAPE_TEMPLATES = {
    "READ>RETURN": {
        "python": "def {name}({param}):\n    {body}\n    return {result}",
        "javascript": "function {name}({param}) {{\n    {body}\n    return {result};\n}}",
        "go": "func {name}({param} string) string {{\n    {body}\n    return {result}\n}}",
    },
    "READ>TRANSFORM>RETURN": {
        "python": "def {name}({param}):\n    {body}\n    return {result}",
        "javascript": "function {name}({param}) {{\n    {body}\n    return {result};\n}}",
    },
    "READ>LOOP>AGGREGATE>RETURN": {
        "python": "def {name}({param}):\n    {body}\n    total = 0\n    for item in {param}:\n        total += item\n    return total",
        "javascript": "function {name}({param}) {{\n    {body}\n    let total = 0;\n    for (let item of {param}) {{\n        total += item;\n    }}\n    return total;\n}}",
    },
}


def _param_for(intent: str) -> str:
    """Pick a sensible parameter name for the intent."""
    return {
        "fetch_api": "user_id", "scrape_web": "url", "query_db": "user_id",
        "read_file": "path", "render_html": "data", "exec_cmd": "cmd",
        "write_file": "path", "send_email": "msg", "parse_json": "data",
        "hash_password": "pw",
    }.get(intent, "data")


def _result_for(intent: str) -> str:
    """Pick a sensible result variable name."""
    return "data" if intent in ("fetch_api", "scrape_web") else "result"


def synthesize(intent: str, shape: str, lang: str = "python", name: str = "fn") -> Optional[str]:
    """Synthesize a function from an intent + shape + language."""
    lib = LIBRARY_TEMPLATES.get(intent, {}).get(lang)
    if not lib:
        return None
    module, call, args_tpl, role = lib
    param = _param_for(intent)
    result = _result_for(intent)

    # build the library call with the param substituted
    args = args_tpl.format(param=param)
    if call:
        lib_call = f"{module}.{call}({args})"
    else:
        lib_call = f"{module}({args})"

    # build the body: READ (fetch) + optional TRANSFORM
    if shape == "READ>TRANSFORM>RETURN":
        transform = TRANSFORM_TEMPLATES.get(intent, {}).get(lang, "")
        transform = transform.format(param=param)
        if intent in ("fetch_api", "scrape_web"):
            # fetch first (requests.get), then process
            fetch = "requests.get(url)" if intent == "scrape_web" else lib_call
            body = f"resp = {fetch}\n    {transform}"
        else:
            body = f"{transform}"
    else:
        body = f"result = {lib_call}"

    tpl = SHAPE_TEMPLATES.get(shape, {}).get(lang)
    if not tpl:
        return None
    return tpl.format(name=name, param=param, body=body, result=result)


def synthesize_any(intent: str, shape: str, lang: str = "python", name: str = "fn") -> Optional[str]:
    """Synthesize code, trying algorithm templates first, then library templates.

    If the intent matches a known algorithm (binary_search, merge_sort, etc.),
    use the algorithm template. Otherwise use the library+shape templates.
    """
    # try algorithm template first
    alg = synthesize_algorithm(intent, lang, name)
    if alg:
        return alg
    # fall back to library+shape
    return synthesize(intent, shape, lang, name)


def verify_shape(code: str, target_shape: str, lang: str = "python") -> Dict:
    """Verify the synthesized code matches the target shape."""
    from code_shape.core.code_shape_core import shape as get_shape
    actual = get_shape(code, lang)
    target_prims = set(target_shape.split(">"))
    actual_prims = set(actual.split(">"))
    overlap = len(target_prims & actual_prims) / len(target_prims) if target_prims else 0
    return {"target": target_shape, "actual": actual, "overlap": round(overlap, 2), "match": overlap >= 0.5}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Shape + Library Code Synthesis (v2) ===")
    for intent, shape in [("fetch_api", "READ>TRANSFORM>RETURN"),
                          ("scrape_web", "READ>TRANSFORM>RETURN"),
                          ("query_db", "READ>TRANSFORM>RETURN"),
                          ("read_file", "READ>RETURN"),
                          ("exec_cmd", "READ>RETURN"),
                          ("write_file", "READ>RETURN"),
                          ("hash_password", "READ>TRANSFORM>RETURN")]:
        code = synthesize(intent, shape, "python", intent)
        if code:
            v = verify_shape(code, shape)
            print(f"\n--- {intent} ({shape}) ---")
            print(code)
            print(f"shape: {v['actual']} (overlap {v['overlap']})")
