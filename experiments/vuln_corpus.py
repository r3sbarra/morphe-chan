#!/usr/bin/env python
"""vuln_corpus.py — Known security vulnerability corpus (CWE patterns).
CWE vulnerability classes. Used to test whether the shape research (shape model,
bug detector, composite shapes) can detect vulnerabilities or find composite-shape
signatures indicating them.

Each entry: (name, cwe, vulnerable_code, clean_code, vuln_type)
"""
import sys
from pathlib import Path

# (name, cwe, vulnerable, clean, vuln_type)
CORPUS = [
    # SQL Injection (CWE-89): string concat into query vs parameterized
    ("sql-injection", "CWE-89",
     "def get_user(username):\n    query = \"SELECT * FROM users WHERE name = '\" + username + \"'\"\n    return db.execute(query)",
     "def get_user(username):\n    query = \"SELECT * FROM users WHERE name = ?\"\n    return db.execute(query, (username,))",
     "injection"),
    # XSS (CWE-79): unsanitized input into HTML vs escaped
    ("xss", "CWE-79",
     "def render(name):\n    return \"<div>Hello \" + name + \"</div>\"",
     "def render(name):\n    safe = html.escape(name)\n    return \"<div>Hello \" + safe + \"</div>\"",
     "injection"),
    # Command Injection (CWE-78): user input into shell vs subprocess list
    ("cmd-injection", "CWE-78",
     "def run(cmd):\n    return os.system(\"ls \" + cmd)",
     "def run(cmd):\n    return subprocess.run([\"ls\", cmd], capture_output=True)",
     "injection"),
    # Path Traversal (CWE-22): user input into path vs sanitized
    ("path-traversal", "CWE-22",
     "def read_file(path):\n    return open(\"/var/data/\" + path).read()",
     "def read_file(path):\n    safe = os.path.basename(path)\n    return open(\"/var/data/\" + safe).read()",
     "injection"),
    # Buffer Overflow (CWE-120): unchecked array access vs bounds-checked
    ("buffer-overflow", "CWE-120",
     "def get(arr, i):\n    return arr[i]",
     "def get(arr, i):\n    if 0 <= i < len(arr):\n        return arr[i]\n    return None",
     "bounds"),
    # Insecure Deserialization (CWE-502): pickle.loads untrusted vs json
    ("deserialization", "CWE-502",
     "def load(data):\n    return pickle.loads(data)",
     "def load(data):\n    return json.loads(data)",
     "unsafe-call"),
    # Hardcoded Credentials (CWE-798): hardcoded password vs env var
    ("hardcoded-cred", "CWE-798",
     "def connect():\n    return db.connect(host, user, \"password123\")",
     "def connect():\n    return db.connect(host, user, os.environ[\"DB_PASS\"])",
     "secret"),
    # Use of eval/exec (CWE-95): dynamic code execution vs safe
    ("eval-use", "CWE-95",
     "def calc(expr):\n    return eval(expr)",
     "def calc(a, b):\n    return a + b",
     "unsafe-call"),
    # Unsafe file write (CWE-22 variant): user input into write path
    ("unsafe-write", "CWE-22",
     "def save(name, data):\n    with open(\"/tmp/\" + name, \"w\") as f:\n        f.write(data)",
     "def save(name, data):\n    safe = os.path.basename(name)\n    with open(\"/tmp/\" + safe, \"w\") as f:\n        f.write(data)",
     "injection"),
    # Race condition (CWE-362): check-then-act vs atomic
    ("race-condition", "CWE-362",
     "def withdraw(acct, amt):\n    if acct.balance >= amt:\n        acct.balance -= amt",
     "def withdraw(acct, amt):\n    with acct.lock:\n        if acct.balance >= amt:\n            acct.balance -= amt",
     "race"),
]


def summary():
    return {"total": len(CORPUS), "cwes": sorted(set(c[1] for c in CORPUS))}


if __name__ == "__main__":
    print("Vulnerability corpus:", summary())
    for name, cwe, v, c, vt in CORPUS:
        print(f"  {name:20s} {cwe:8s} [{vt}]")
