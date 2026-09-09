#!/usr/bin/env python
"""clone_corpus.py — Curated labeled clone corpus for code-vector experiments.

Each entry: (code_a, code_b, is_clone, intent_label).

- True clones: same behavior, different syntax (renamed vars, reordered,
  different idioms, added intermediate vars).
- False clones: different behavior, possibly sharing keywords/structure.

Covers diverse intents: arithmetic, string, list, sort, search, recursion,
state mutation, filtering, aggregation, I/O.
"""
import sys
from pathlib import Path

# ── True clones (semantic clones, different syntax) ─────────────────────────
TRUE_CLONES = [
    # arithmetic
    ("def add(a, b):\n    return a + b",
     "def sum_two(x, y):\n    result = x + y\n    return result", "arith"),
    ("def area(r):\n    return 3.14159 * r * r",
     "def circle_area(radius):\n    pi = 3.14159\n    return pi * radius * radius", "arith"),
    ("def avg(nums):\n    return sum(nums) / len(nums)",
     "def mean(values):\n    total = 0\n    for v in values:\n        total += v\n    return total / len(values)", "arith"),
    # string
    ("def greet(name):\n    return 'Hello, ' + name + '!'",
     "def hello(person):\n    msg = 'Hello, ' + person + '!'\n    return msg", "string"),
    ("def upper(s):\n    return s.upper()",
     "def to_uppercase(text):\n    return text.upper()", "string"),
    # list / filter / aggregate
    ("def evens(nums):\n    return [n for n in nums if n % 2 == 0]",
     "def even_numbers(items):\n    result = []\n    for x in items:\n        if x % 2 == 0:\n            result.append(x)\n    return result", "list"),
    ("def total(nums):\n    return sum(nums)",
     "def sum_all(values):\n    acc = 0\n    for v in values:\n        acc = acc + v\n    return acc", "list"),
    # sort / search
    ("def sort_asc(arr):\n    return sorted(arr)",
     "def ascending(items):\n    return sorted(items)", "sort"),
    ("def find_idx(arr, x):\n    return arr.index(x)",
     "def locate(items, target):\n    for i in range(len(items)):\n        if items[i] == target:\n            return i\n    return -1", "search"),
    # recursion
    ("def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)",
     "def factorial(num):\n    if num <= 1:\n        return 1\n    return num * factorial(num - 1)", "recursion"),
    # state mutation
    ("def inc(counter):\n    counter += 1\n    return counter",
     "def increment(count):\n    count = count + 1\n    return count", "state"),
    # max/min
    ("def biggest(a, b):\n    return a if a > b else b",
     "def larger(x, y):\n    if x > y:\n        return x\n    return y", "arith"),
]

# ── False clones (different behavior, may share structure) ──────────────────
FALSE_CLONES = [
    ("def add(a, b):\n    return a + b",
     "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr", "arith-vs-sort"),
    ("def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)",
     "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)", "recursion"),
    ("def is_even(n):\n    return n % 2 == 0",
     "def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, n):\n        if n % i == 0:\n            return False\n    return True", "predicate"),
    ("def greet(name):\n    return 'Hello, ' + name + '!'",
     "def parse_csv(line):\n    return line.split(',')", "string"),
    ("def total(nums):\n    return sum(nums)",
     "def reverse_list(items):\n    return items[::-1]", "list"),
    ("def sort_asc(arr):\n    return sorted(arr)",
     "def dedupe(items):\n    seen = set()\n    out = []\n    for x in items:\n        if x not in seen:\n            seen.add(x)\n            out.append(x)\n    return out", "sort-vs-dedupe"),
    ("def find_idx(arr, x):\n    return arr.index(x)",
     "def count_occurrences(arr, x):\n    return arr.count(x)", "search-vs-count"),
    ("def inc(counter):\n    counter += 1\n    return counter",
     "def reset(counter):\n    counter = 0\n    return counter", "state"),
    ("def biggest(a, b):\n    return a if a > b else b",
     "def smallest(a, b):\n    return a if a < b else b", "max-vs-min"),
    ("def upper(s):\n    return s.upper()",
     "def strip_ws(s):\n    return s.strip()", "string"),
    ("def evens(nums):\n    return [n for n in nums if n % 2 == 0]",
     "def odds(nums):\n    return [n for n in nums if n % 2 != 0]", "even-vs-odd"),
    ("def avg(nums):\n    return sum(nums) / len(nums)",
     "def median(nums):\n    s = sorted(nums)\n    n = len(s)\n    return s[n // 2]", "mean-vs-median"),
]

# Full corpus: (a, b, is_clone, label)
CORPUS = [(a, b, True, lbl) for a, b, lbl in TRUE_CLONES] + \
         [(a, b, False, lbl) for a, b, lbl in FALSE_CLONES]


def summary():
    n_true = sum(1 for c in CORPUS if c[2])
    n_false = len(CORPUS) - n_true
    return {"total": len(CORPUS), "true_clones": n_true, "false_clones": n_false}


if __name__ == "__main__":
    print("Corpus:", summary())
    for i, (a, b, is_clone, lbl) in enumerate(CORPUS):
        print(f"  {i:2d} {'CLONE' if is_clone else 'DIFF '} [{lbl:16s}] {a.splitlines()[0][:40]}")
