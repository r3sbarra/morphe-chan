#!/usr/bin/env python
"""experiment_token_efficiency.py — Code synth + LLM vs raw LLM token usage.
LLM request spends FEWER tokens to generate the same (or better) code.

Calls ollama DIRECTLY (no gateway context injection) for clean token counts.

Method:
  1. RAW LLM: ask the LLM to write a function from a natural-language prompt.
  2. SYNTH+LLM: run the shape+library synthesizer to produce a draft, then ask
     the LLM to refine/fix the draft.
  3. Compare prompt + completion tokens.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from code_shape.synthesis.shape_library_synth import synthesize

OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "deepseek-v4-flash:cloud"


def llm_chat(prompt, system=None, max_tokens=200):
    """Call ollama directly. Returns (text, prompt_tokens, completion_tokens)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(OLLAMA, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    return (data["message"]["content"],
            data.get("prompt_eval_count", 0),
            data.get("eval_count", 0))


CASES = [
    ("fetch_api", "READ>TRANSFORM>RETURN",
     "Write a Python function that fetches a user's data from an API endpoint "
     "using requests, parses the JSON response, and returns the user's name and email."),
    ("scrape_web", "READ>TRANSFORM>RETURN",
     "Write a Python function that scrapes a webpage using requests and "
     "BeautifulSoup, extracts the page title and all links, and returns them."),
    ("query_db", "READ>TRANSFORM>RETURN",
     "Write a Python function that queries a SQLite database for a user by id "
     "and returns the user record."),
    ("read_file", "READ>RETURN",
     "Write a Python function that reads a file from a path and returns its contents."),
]


def main():
    print("=== Token Efficiency: Code Synth + LLM vs Raw LLM (direct ollama) ===")
    print(f"Model: {MODEL}\n")
    print(f"{'case':12s} {'raw_prompt':>10s} {'raw_comp':>9s} {'raw_total':>9s} "
          f"{'synth_prompt':>12s} {'synth_comp':>10s} {'synth_total':>11s} {'saved':>6s}")

    total_raw = 0
    total_synth = 0
    for intent, shape, prompt in CASES:
        # 1. RAW LLM
        raw_msg, raw_p, raw_c = llm_chat(prompt, system="You are a code generator. Write clean, correct Python code.")
        raw_total = raw_p + raw_c

        # 2. SYNTH + LLM
        draft = synthesize(intent, shape, "python", intent)
        synth_msg, synth_p, synth_c = llm_chat(
            f"Draft code:\n```python\n{draft}\n```\n\nTask: {prompt}",
            system="You are a code refiner. The draft is close but may have bugs. Fix and complete it into clean, correct Python code.")
        synth_total = synth_p + synth_c

        saved = raw_total - synth_total
        total_raw += raw_total
        total_synth += synth_total
        print(f"{intent:12s} {raw_p:>10d} {raw_c:>9d} {raw_total:>9d} "
              f"{synth_p:>12d} {synth_c:>10d} {synth_total:>11d} {saved:>+6d}")

    print(f"\n{'TOTAL':12s} {'':>10s} {'':>9s} {total_raw:>9d} "
          f"{'':>12s} {'':>10s} {total_synth:>11d} {total_raw - total_synth:>+6d}")
    pct = (total_raw - total_synth) / total_raw * 100 if total_raw else 0
    print(f"\nToken savings: {pct:.1f}%")


if __name__ == "__main__":
    main()
