#!/usr/bin/env python
"""bug_bounty_corpus.py — Expanded bug-bounty vulnerability corpus.
patterns across many CWE classes, with vulnerable + clean versions.

Each entry: (name, cwe, vulnerable_code, clean_code, vuln_type)
"""
import sys
from pathlib import Path

# (name, cwe, vulnerable, clean, vuln_type)
CORPUS = [
    # ── Injection ───────────────────────────────────────────────────────────
    ("sql-injection", "CWE-89",
     "def get_user(request):\n    name = request.form['name']\n    return db.execute('SELECT * FROM users WHERE name = ' + name)",
     "def get_user(request):\n    name = request.form['name']\n    return db.execute('SELECT * FROM users WHERE name = ?', (name,))",
     "injection"),
    ("command-injection", "CWE-78",
     "def ping(request):\n    host = request.args['host']\n    return os.system('ping ' + host)",
     "def ping(request):\n    host = request.args['host']\n    return subprocess.run(['ping', host], capture_output=True)",
     "injection"),
    ("ldap-injection", "CWE-90",
     "def auth(request):\n    user = request.form['user']\n    return ldap.search('(uid=' + user + ')')",
     "def auth(request):\n    user = request.form['user']\n    return ldap.search('(uid=' + ldap.escape(user) + ')')",
     "injection"),
    ("template-injection", "CWE-1336",
     "def render(request):\n    tpl = request.args['template']\n    return Template(tpl).render()",
     "def render(request):\n    tpl = request.args['template']\n    return Template(tpl).render(safe=True)",
     "injection"),
    ("header-injection", "CWE-113",
     "def redirect(request):\n    url = request.args['url']\n    resp = Response()\n    resp.headers['Location'] = url\n    return resp",
     "def redirect(request):\n    url = request.args['url']\n    if not url.startswith('https://'):\n        return 400\n    resp = Response()\n    resp.headers['Location'] = url\n    return resp",
     "injection"),
    ("log-injection", "CWE-117",
     "def log(request):\n    user = request.args['user']\n    logger.info('User: ' + user)",
     "def log(request):\n    user = request.args['user']\n    logger.info('User: ' + user.replace('\\n', ''))",
     "injection"),
    # ── XSS ─────────────────────────────────────────────────────────────────
    ("reflected-xss", "CWE-79",
     "def search(request):\n    q = request.args['q']\n    return '<div>Results for ' + q + '</div>'",
     "def search(request):\n    q = request.args['q']\n    return '<div>Results for ' + html.escape(q) + '</div>'",
     "xss"),
    ("stored-xss", "CWE-79",
     "def comment(request):\n    text = request.form['text']\n    db.execute('INSERT INTO comments (text) VALUES (?)', (text,))\n    return render_comments()",
     "def comment(request):\n    text = html.escape(request.form['text'])\n    db.execute('INSERT INTO comments (text) VALUES (?)', (text,))\n    return render_comments()",
     "xss"),
    # ── Path / File ─────────────────────────────────────────────────────────
    ("path-traversal", "CWE-22",
     "def download(request):\n    f = request.args['file']\n    return open('/var/www/' + f).read()",
     "def download(request):\n    f = os.path.basename(request.args['file'])\n    return open('/var/www/' + f).read()",
     "path"),
    ("arbitrary-file-write", "CWE-22",
     "def save(request):\n    name = request.form['name']\n    with open('/tmp/' + name, 'w') as f:\n        f.write(request.form['data'])",
     "def save(request):\n    name = os.path.basename(request.form['name'])\n    with open('/tmp/' + name, 'w') as f:\n        f.write(request.form['data'])",
     "path"),
    # ── SSRF / XXE / Deserialization ────────────────────────────────────────
    ("ssrf", "CWE-918",
     "def fetch(request):\n    url = request.args['url']\n    return requests.get(url).text",
     "def fetch(request):\n    url = request.args['url']\n    if not url.startswith('https://internal.'):\n        return 400\n    return requests.get(url).text",
     "ssrf"),
    ("xxe", "CWE-611",
     "def parse(request):\n    xml = request.data\n    return parse_xml(xml)",
     "def parse(request):\n    xml = request.data\n    return parse_xml(xml, resolve_entities=False)",
     "xxe"),
    ("insecure-deserialization", "CWE-502",
     "def load(request):\n    data = request.data\n    return pickle.loads(data)",
     "def load(request):\n    data = request.data\n    return json.loads(data)",
     "deserialize"),
    # ── Auth / Access Control ──────────────────────────────────────────────
    ("idor", "CWE-639",
     "def get_profile(request):\n    uid = request.args['uid']\n    return db.execute('SELECT * FROM users WHERE id = ?', (uid,))",
     "def get_profile(request):\n    uid = request.args['uid']\n    if uid != request.session['user_id']:\n        return 403\n    return db.execute('SELECT * FROM users WHERE id = ?', (uid,))",
     "access"),
    ("open-redirect", "CWE-601",
     "def login_redirect(request):\n    next_url = request.args['next']\n    return redirect(next_url)",
     "def login_redirect(request):\n    next_url = request.args['next']\n    if not next_url.startswith('/'):\n        return 400\n    return redirect(next_url)",
     "access"),
    ("csrf", "CWE-352",
     "def transfer(request):\n    amt = request.form['amount']\n    return transfer_money(request.session['user'], amt)",
     "def transfer(request):\n    if request.form['csrf_token'] != request.session['csrf_token']:\n        return 403\n    amt = request.form['amount']\n    return transfer_money(request.session['user'], amt)",
     "access"),
    # ── Code Execution / Secrets ────────────────────────────────────────────
    ("eval-rce", "CWE-95",
     "def calc(request):\n    expr = request.form['expr']\n    return eval(expr)",
     "def calc(request):\n    a = int(request.form['a'])\n    b = int(request.form['b'])\n    return a + b",
     "code-exec"),
    ("hardcoded-secret", "CWE-798",
     "def api():\n    return requests.get('https://api.x.com', headers={'Authorization': 'Bearer sk_live_1234567890'})",
     "def api():\n    return requests.get('https://api.x.com', headers={'Authorization': 'Bearer ' + os.environ['API_KEY']})",
     "secret"),
    ("insecure-random", "CWE-330",
     "def reset_token():\n    return str(random.random())",
     "def reset_token():\n    return secrets.token_hex(16)",
     "crypto"),
    ("weak-hash", "CWE-327",
     "def store_password(pw):\n    return hashlib.md5(pw.encode()).hexdigest()",
     "def store_password(pw):\n    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt())",
     "crypto"),
]


def summary():
    return {"total": len(CORPUS), "cwes": sorted(set(c[1] for c in CORPUS))}


if __name__ == "__main__":
    print("Bug-bounty corpus:", summary())
    for name, cwe, v, c, vt in CORPUS:
        print(f"  {name:24s} {cwe:8s} [{vt}]")
