#!/usr/bin/env python
"""real_cve_corpus.py — Real-world CVE vulnerability patterns.
vulnerable code and the CORRECT function/source that should be flagged.

Each entry: (cve, name, vulnerable_code, expected_vuln_type, expected_source)
"""
import sys
from pathlib import Path

# (cve, name, vulnerable_code, expected_type, expected_source)
REAL_CVES = [
    # CVE-2017-5638: Apache Struts RCE via OGNL injection in Content-Type header
    ("CVE-2017-5638", "struts-ognl-rce",
     "def handle_request(request):\n    content_type = request.headers['Content-Type']\n    return execute_ognl(content_type)",
     "CMD_INJECTION", "request.headers"),
    # CVE-2019-15107: Webmin command injection via password change
    ("CVE-2019-15107", "webmin-cmd-inject",
     "def change_password(user, newpass):\n    cmd = 'echo ' + newpass + ' | passwd ' + user\n    return os.system(cmd)",
     "CMD_INJECTION", "newpass"),
    # CVE-2018-7600: Drupalgeddon2 RCE via form API
    ("CVE-2018-7600", "drupal-rce",
     "def process_form(form):\n    data = form['mail']\n    return eval(data)",
     "EVAL_USE", "form['mail']"),
    # CVE-2021-44228: Log4Shell JNDI injection
    ("CVE-2021-44228", "log4shell",
     "def log_message(msg):\n    return jndi.lookup(msg)",
     "EVAL_USE", "msg"),
    # CVE-2014-0160: Heartbleed buffer over-read
    ("CVE-2014-0160", "heartbleed",
     "def heartbeat(payload, length):\n    return payload[0:length]",
     "BUFFER_OVERFLOW", "length"),
    # CVE-2017-0144: EternalBlue buffer overflow
    ("CVE-2017-0144", "eternalblue",
     "def parse_smb(data, offset):\n    return data[offset]",
     "BUFFER_OVERFLOW", "offset"),
    # SQL injection (classic, e.g. CVE-2019-19781 style)
    ("CVE-2019-19781", "citrix-sqli",
     "def get_user(request):\n    name = request.args['name']\n    return db.execute('SELECT * FROM users WHERE name = ' + name)",
     "SQL_INJECTION", "request.args"),
    # Path traversal (CVE-2020-3452 style)
    ("CVE-2020-3452", "cisco-path-traversal",
     "def read_file(request):\n    path = request.args['file']\n    return open('/var/www/' + path).read()",
     "PATH_TRAVERSAL", "request.args"),
]


def summary():
    return {"total": len(REAL_CVES), "cwes": sorted(set(c[0] for c in REAL_CVES))}


if __name__ == "__main__":
    print("Real CVE corpus:", summary())
    for cve, name, code, vtype, src in REAL_CVES:
        print(f"  {cve:14s} {name:22s} [{vtype}] source={src}")
