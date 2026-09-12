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
     "OGNL_INJECTION", "request.headers"),
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
     "JNDI_INJECTION", "msg"),
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
    # CVE-2023-34362: MOVEit Transfer SQL Injection
    ("CVE-2023-34362", "moveit-sqli",
     "def handle_session(request):\n    session_id = request.headers['X-Session-Id']\n    return db.execute('SELECT * FROM active_sessions WHERE id = ' + session_id)",
     "SQL_INJECTION", "request.headers"),
    # CVE-2021-41773: Apache HTTP Server Path Traversal
    ("CVE-2021-41773", "apache-path-traversal",
     "def serve_file(request):\n    url_path = request.args['path']\n    return open('/usr/local/apache2/htdocs/' + url_path).read()",
     "PATH_TRAVERSAL", "request.args"),
    # CVE-2021-26855: Microsoft Exchange ProxyLogon SSRF
    ("CVE-2021-26855", "proxylogon-ssrf",
     "def proxy_backend(request):\n    backend_url = request.cookies['X-BEResource']\n    return requests.get(backend_url).text",
     "SSRF", "request.cookies"),
    # CVE-2023-46604: Apache ActiveMQ OpenWire Deserialization RCE
    ("CVE-2023-46604", "activemq-deserialization",
     "def process_openwire(request):\n    data = request.data\n    return pickle.loads(data)",
     "DESERIALIZATION", "request.data"),
    # CVE-2020-11022: jQuery XSS
    ("CVE-2020-11022", "jquery-xss",
     "def render_query(request):\n    user_input = request.args['q']\n    return '<div>Result: ' + user_input + '</div>'",
     "XSS", "request.args"),
    # CVE-2019-8341: Jinja2 Server-Side Template Injection
    ("CVE-2019-8341", "jinja2-ssti",
     "def render_greeting(request):\n    name = request.args['name']\n    return Template(name).render()",
     "TEMPLATE_INJECTION", "request.args"),
    # CVE-2023-22515: Atlassian Confluence Broken Access Control / IDOR
    ("CVE-2023-22515", "confluence-broken-auth",
     "def setup_admin(request):\n    user_id = request.args['userId']\n    return db.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
     "IDOR", "request.args"),
    # CVE-2020-2509: QNAP QTS Hardcoded Credentials
    ("CVE-2020-2509", "qnap-hardcoded-cred",
     "def admin_login():\n    api_key = 'Bearer sk_live_998877665544332211'\n    return requests.post('https://internal/auth', headers={'Authorization': api_key})",
     "HARDCODED_CRED", "api_key"),
]


def summary():
    return {"total": len(REAL_CVES), "cwes": sorted(set(c[0] for c in REAL_CVES))}


if __name__ == "__main__":
    print("Real CVE corpus:", summary())
    for cve, name, code, vtype, src in REAL_CVES:
        print(f"  {cve:14s} {name:22s} [{vtype}] source={src}")
