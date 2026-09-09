#!/usr/bin/env python
"""experiment_core_agnostic.py — Validate the code-agnostic core with language
adapters + recursive true shape across 13 languages.
  1. Adapter detection for all 13 languages
  2. Same behavior (sum) → same true shape in all languages
  3. Recursive decomposition: a program's true shape inherits callee structure
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from code_shape.core.code_shape_core import get_adapter, shape, true_similarity, recursive_shape, ADAPTERS

# Same behavior (sum a list) in 13 languages
SUM_SAMPLES = {
    "python": "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
    "javascript": "function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}",
    "typescript": "function sumList(nums: number[]): number {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}",
    "java": "int sumList(int[] nums) {\n    int total = 0;\n    for (int n : nums) {\n        total += n;\n    }\n    return total;\n}",
    "c": "int sum_list(int nums[], int len) {\n    int total = 0;\n    for (int i = 0; i < len; i++) {\n        total += nums[i];\n    }\n    return total;\n}",
    "cpp": "int sum_list(std::vector<int>& nums) {\n    int total = 0;\n    for (int n : nums) {\n        total += n;\n    }\n    return total;\n}",
    "csharp": "int SumList(int[] nums) {\n    int total = 0;\n    foreach (int n in nums) {\n        total += n;\n    }\n    return total;\n}",
    "go": "func sumList(nums []int) int {\n    total := 0\n    for _, n := range nums {\n        total += n\n    }\n    return total\n}",
    "rust": "fn sum_list(nums: &[i32]) -> i32 {\n    let mut total = 0;\n    for n in nums {\n        total += n;\n    }\n    return total;\n}",
    "ruby": "def sum_list(nums)\n    total = 0\n    nums.each do |n|\n        total += n\n    end\n    return total\nend",
    "php": "function sum_list($nums) {\n    $total = 0;\n    foreach ($nums as $n) {\n        $total += $n;\n    }\n    return $total;\n}",
    "swift": "func sumList(_ nums: [Int]) -> Int {\n    var total = 0\n    for n in nums {\n        total += n\n    }\n    return total\n}",
    "kotlin": "fun sumList(nums: List<Int>): Int {\n    var total = 0\n    for (n in nums) {\n        total += n\n    }\n    return total\n}",
}

# Program with helper (recursive true shape should inherit callee structure)
PROG = '''
def add(a, b):
    return a + b

def double(x):
    return add(x, x)

def main(nums):
    total = 0
    for n in nums:
        total = double(n)
    return total
'''


def main():
    print("=== Code-Agnostic Core: Adapter Detection (13 languages) ===")
    correct = 0
    for lang, code in SUM_SAMPLES.items():
        a = get_adapter(code, lang)
        ok = a.name == lang
        correct += ok
        print(f"  {lang:12s} -> adapter {a.name:12s} {'OK' if ok else 'XX'}")
    print(f"  adapter detection: {correct}/{len(SUM_SAMPLES)}")

    print("\n=== Same behavior (sum) → true shape in all languages ===")
    shapes = {}
    for lang, code in SUM_SAMPLES.items():
        shapes[lang] = shape(code, lang)
    # check all shapes are the same
    first = shapes["python"]
    same = all(s == first for s in shapes.values())
    print(f"  all 13 languages same shape: {same}")
    print(f"  shape: {first}")

    print("\n=== Cross-language true similarity ===")
    py = SUM_SAMPLES["python"]
    sims = []
    for lang, code in SUM_SAMPLES.items():
        if lang == "python":
            continue
        s = true_similarity(py, code, "python", lang)
        sims.append(s)
    print(f"  mean cross-language true similarity: {sum(sims)/len(sims):.3f}")

    print("\n=== Recursive true shape (program with helper) ===")
    own = recursive_shape(PROG, "python", max_depth=0)
    true = recursive_shape(PROG, "python", max_depth=5)
    print(f"  own shape:  {shape(PROG, 'python')}")
    print(f"  true shape: {shape(PROG, 'python')}")
    print(f"  RECURSE own={own['RECURSE']} true={true['RECURSE']} (recursive inheritance)")
    print(f"  AGGREGATE own={own['AGGREGATE']} true={true['AGGREGATE']}")


if __name__ == "__main__":
    main()
