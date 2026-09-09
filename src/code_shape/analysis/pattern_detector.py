#!/usr/bin/env python
"""pattern_detector.py — Detect design patterns, data structures, concurrency.
  - DESIGN PATTERNS: singleton, factory, observer, decorator, adapter
  - DATA STRUCTURES: stack, queue, hashmap, linked_list, tree, graph
  - CONCURRENCY: producer_consumer, thread_pool, lock, async
  - RESILIENCE: retry, circuit_breaker, rate_limit, cache
  - OTHER: pagination, validation, serialization, logging

Each pattern has a characteristic shape/flow signature. This extends the
algorithm detector to a broader set of recognizable code patterns.

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List

from code_shape.core.code_shape_core import shape as get_shape

# ── Pattern signatures: (name, key_primitives, distinguishing_features) ─────
PATTERNS = [
    # Design patterns
    ("singleton", ["ASSIGN", "BRANCH"],
     {"instance": r"__instance\s*=|_instance\s*=|getInstance\s*\(|instance\s*=\s*None"}),
    ("factory", ["ASSIGN", "RETURN"],
     {"create": r"def\s+create_\w+|Factory\s*\(|def\s+make_\w+|def\s+build_\w+"}),
    ("observer", ["ASSIGN", "BRANCH"],
     {"subscribe": r"\.subscribe\s*\(|\.addListener\s*\(|\.on\s*\(|notify_observers|\.emit\s*\("}),
    ("decorator", ["ASSIGN", "RETURN"],
     {"deco": r"@\w+\.\w+|def\s+decorator|@staticmethod|@classmethod|@property"}),
    ("adapter", ["ASSIGN", "RETURN"],
     {"adapt": r"def\s+adapt|Adapter\s*\(|\.adapt\s*\("}),
    # Data structures
    ("stack", ["ASSIGN", "BRANCH"],
     {"stack": r"\.push\s*\(|\.pop\s*\(|stack\s*=|LIFO"}),
    ("queue", ["ASSIGN", "BRANCH"],
     {"queue": r"\.enqueue\s*\(|\.dequeue\s*\(|queue\s*=|FIFO|collections\.deque|\bdeque\b|\.put\s*\(|\.get\s*\(|\.popleft\s*\(|\.append\s*\([^)]*queue"}),
    ("hashmap", ["ASSIGN", "SEARCH", "BRANCH"],
     {"map": r"\.get\s*\([^)]*default|dict\s*=|HashMap|seen\s*=|cache\s*=\s*\{\}"}),
    ("linked_list", ["ASSIGN", "BRANCH"],
     {"list": r"\.next\s*=|\.prev\s*=|ListNode|\.head\s*=|\.tail\s*="}),
    ("tree", ["RECURSE", "BRANCH"],
     {"tree": r"\.left\s*=|\.right\s*=|TreeNode|\.children\s*=|root\."}),
    ("graph", ["LOOP", "BRANCH", "ASSIGN"],
     {"graph": r"adjacency|graph\s*=|\.neighbors|\.edges\s*="}),
    # Concurrency
    ("producer_consumer", ["LOOP", "ASSIGN"],
     {"pc": r"queue\.put\s*\(|queue\.get\s*\(|producer|consumer"}),
    ("thread_pool", ["ASSIGN", "LOOP"],
     {"pool": r"ThreadPool|Executor|\.submit\s*\(|Pool\s*\(|concurrent\.futures"}),
    ("lock", ["ASSIGN", "BRANCH"],
     {"lock": r"\.acquire\s*\(|\.release\s*\(|with\s+.*lock|Lock\s*\(|mutex|RLock"}),
    ("async", ["ASSIGN", "BRANCH"],
     {"async": r"async\s+def|await\s+|asyncio\.|\.create_task\s*\("}),
    # Resilience
    ("retry", ["LOOP", "BRANCH"],
     {"retry": r"retry|max_retries|attempts\s*=|backoff|for\s+attempt"}),
    ("circuit_breaker", ["BRANCH", "ASSIGN"],
     {"cb": r"circuit_breaker|trip\s*=|half_open|failure_threshold|open\s*=\s*True"}),
    ("rate_limit", ["BRANCH", "ASSIGN"],
     {"rl": r"rate_limit|throttle|token_bucket|leaky_bucket|min_interval"}),
    ("cache", ["ASSIGN", "BRANCH", "SEARCH"],
     {"cache": r"cache\s*=|lru_cache|memoiz|@cache|\.get\s*\([^)]*cache"}),
    # Other
    ("pagination", ["LOOP", "BRANCH"],
     {"page": r"page_size|offset\s*=|limit\s*=|paginate|per_page"}),
    ("validation", ["BRANCH", "COMPARE"],
     {"validate": r"validate\s*\(|is_valid|check\s*\(|assert\s+|if\s+not\s+\w+\.(?:is|startswith|endswith)"}),
    ("serialization", ["ASSIGN", "RETURN"],
     {"ser": r"\.to_json\s*\(|\.from_json\s*\(|serialize\s*\(|deserialize\s*\(|json\.dumps|json\.loads"}),
    ("logging", ["ASSIGN"],
     {"log": r"logger\.|logging\.|log\.info|log\.error|log\.warning"}),
]


def detect_patterns(code: str, lang: str = "python") -> List[Dict]:
    """Detect design/data/concurrency patterns from shape + features."""
    shape_str = get_shape(code, lang)
    prims = set(shape_str.split(">"))
    results = []
    for name, key_prims, features in PATTERNS:
        overlap = len(set(key_prims) & prims) / len(key_prims)
        feature_hits = 0
        for feat, pat in features.items():
            if re.search(pat, code, re.IGNORECASE):
                feature_hits += 1
        # require at least one feature hit
        if feature_hits == 0:
            continue
        score = 0.4 * overlap + 0.6 * min(1.0, feature_hits / max(1, len(features)))
        if score >= 0.4:
            results.append({
                "pattern": name,
                "score": round(score, 2),
                "shape": shape_str,
                "features_hit": feature_hits,
            })
    results.sort(key=lambda x: -x["score"])
    return results


def pattern_signature(code: str, lang: str = "python") -> str:
    """Human-readable pattern signature."""
    det = detect_patterns(code, lang)
    if not det:
        return "NONE"
    return ", ".join(f"{d['pattern']}({d['score']})" for d in det[:3])


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    samples = {
        "singleton": "class Config:\n    _instance = None\n    def __new__(cls):\n        if cls._instance is None:\n            cls._instance = super().__new__(cls)\n        return cls._instance",
        "factory": "def create_user(name):\n    return User(name)",
        "stack": "def process():\n    stack = []\n    stack.push(x)\n    return stack.pop()",
        "queue": "from collections import deque\ndef process():\n    q = deque()\n    q.append(x)\n    return q.popleft()",
        "retry": "def fetch(url):\n    for attempt in range(3):\n        try:\n            return requests.get(url)\n        except:\n            time.sleep(2 ** attempt)",
        "cache": "from functools import lru_cache\n@lru_cache\ndef fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)",
        "thread_pool": "from concurrent.futures import ThreadPoolExecutor\ndef run():\n    with ThreadPoolExecutor() as ex:\n        ex.submit(work, x)",
        "simple_add": "def add(a, b):\n    return a + b",
    }
    print("=== Pattern detection ===")
    for name, code in samples.items():
        det = detect_patterns(code)
        print(f"{name:14s} -> {[d['pattern'] for d in det]}")
