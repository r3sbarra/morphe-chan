#!/usr/bin/env python
"""experiment_crosslang_clone.py — Cross-language clone detection via
code-agnostic shape.
SAME behavior implemented in DIFFERENT languages (cross-language clones).

This is a direct application of the multi-language shape work: if the shape is
truly code-agnostic, then a sum function in Python and a sum function in Go
should have high shape similarity (they're cross-language clones), while a sum
in Python and a sort in Go should be low.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from code_shape.core.code_shape_core import true_similarity, shape

# Same behavior (sum) in 4 languages
SUM = {
    "python": "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
    "go": "func sumList(nums []int) int {\n    total := 0\n    for _, n := range nums {\n        total += n\n    }\n    return total\n}",
    "rust": "fn sum_list(nums: &[i32]) -> i32 {\n    let mut total = 0;\n    for n in nums {\n        total += n;\n    }\n    return total;\n}",
    "js": "function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}",
}

# Different behavior (sort) in Python + Go
SORT = {
    "python": "def sort_asc(arr):\n    return sorted(arr)",
    "go": "func sortAsc(arr []int) []int {\n    sort.Ints(arr)\n    return arr\n}",
}

# Different behavior (filter evens) in Python
EVENS = "def evens(nums):\n    return [n for n in nums if n % 2 == 0]"


def main():
    print("=== Cross-Language Clone Detection (code-agnostic shape) ===")
    print("\nSame behavior (sum) across languages — should be HIGH:")
    langs = list(SUM.keys())
    for i in range(len(langs)):
        for j in range(i + 1, len(langs)):
            a, b = langs[i], langs[j]
            s = true_similarity(SUM[a], SUM[b], a, b)
            print(f"  {a:8s} vs {b:8s}: {s:.3f}  (clone={s >= 0.7})")

    print("\nDifferent behavior — should be LOW:")
    print(f"  py sum vs py evens: {true_similarity(SUM['python'], EVENS, 'python', 'python'):.3f}")
    print(f"  py sum vs go sort:  {true_similarity(SUM['python'], SORT['go'], 'python', 'go'):.3f}")
    print(f"  go sum vs py sort:  {true_similarity(SUM['go'], SORT['python'], 'go', 'python'):.3f}")

    print("\n=== Cross-language clone detection accuracy ===")
    # true clones: same behavior across languages
    # false clones: different behavior
    correct = 0
    total = 0
    # true clones (all sum pairs)
    for i in range(len(langs)):
        for j in range(i + 1, len(langs)):
            s = true_similarity(SUM[langs[i]], SUM[langs[j]], langs[i], langs[j])
            correct += (s >= 0.7)
            total += 1
    # false clones
    for lang in langs:
        s = true_similarity(SUM[lang], EVENS, lang, "python")
        correct += (s < 0.7)
        total += 1
        s2 = true_similarity(SUM[lang], SORT["python"], lang, "python")
        correct += (s2 < 0.7)
        total += 1
    print(f"  accuracy: {correct}/{total}")


if __name__ == "__main__":
    main()
