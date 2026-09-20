"""Regression tests for obscure vulnerability detection:
reflective sink calls + broadened secret patterns.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.security.precise_issues import (
    find_precise_issues, find_buffer_overflows,
)


def _types(code):
    return [i["type"] for i in find_precise_issues(code) + find_buffer_overflows(code)]


def test_reflective_getattr_system():
    # getattr(os, "system")(...) bypasses the literal os.system() sink.
    code = 'import os\ndef f(c):\n    getattr(os, "system")(c)'
    assert "CMD_INJECTION" in _types(code)


def test_reflective_getattr_safe_not_flagged():
    code = 'def f(o):\n    return getattr(o, "name")'
    assert "CMD_INJECTION" not in _types(code)


def test_sk_live_api_key():
    code = "API_SECRET = 'sk-live-abcdefghijklmnopqrstuvwxyz123456'"
    assert "HARDCODED_CRED" in _types(code)


def test_jwt_two_segment():
    code = "JWT_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIx'"
    assert "HARDCODED_CRED" in _types(code)


def test_jwt_three_segment():
    code = "jwt = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.somesig'"
    assert "HARDCODED_CRED" in _types(code)


def test_compound_secret_var():
    code = "MY_ACCESS_TOKEN = 'supersecretvalue12345678'"
    assert "HARDCODED_CRED" in _types(code)


def test_secret_negatives():
    assert "HARDCODED_CRED" not in _types('name = "bob"')
    assert "HARDCODED_CRED" not in _types("url = 'https://example.com/api'")
    assert "HARDCODED_CRED" not in _types('s = "sk-x"')  # too short


def test_alias_eval():
    code = "execute = eval\ndef f(x):\n    execute(x)"
    assert "EVAL_USE" in _types(code)


def test_alias_os_system():
    code = "import os\ndef f(c):\n    run = os.system\n    run(c)"
    assert "CMD_INJECTION" in _types(code)


def test_alias_subprocess():
    code = "import subprocess\ndef f(c):\n    p = subprocess.call\n    return p(c, shell=True)"
    assert "CMD_INJECTION" in _types(code)


def test_alias_not_invoked_clean():
    assert "CMD_INJECTION" not in _types("run = os.system")
    assert "CMD_INJECTION" not in _types("def f():\n    run = helper\n    run(x)")


def test_js_multiline_innerhtml_compound():
    code = "function f() {\n  el.innerHTML += user\n}"
    assert "XSS" in _types(code)


# ---- Round 3: more obscure sinks/variants ----
def test_msgpack_deserialization():
    assert "DESERIALIZATION" in _types(
        "import msgpack\ndef f(b):\n    return msgpack.unpackb(b)")


def test_buffer_slice_by_param():
    assert "BUFFER_OVERFLOW" in _types("def f(a, i):\n    return a[i:i+2]")


def test_xss_outerhtml():
    assert "XSS" in _types("def f(x):\n    el.outerHTML = x")


def test_xss_setattribute_href():
    assert "XSS" in _types('def f(x):\n    el.setAttribute("href", x)')


def test_xss_insertadjacenthtml():
    assert "XSS" in _types('def f(x):\n    el.insertAdjacentHTML("beforeend", x)')


def test_weak_des_crypto():
    assert "WEAK_HASH" in _types("from Crypto.Cipher import DES\ndef f():\n    DES.new(key)")


def test_setattribute_safe_constant_clean():
    assert "XSS" not in _types('el.setAttribute("href", "/static")')


def test_console_log_injection():
    # Express/Nodemon console.log to server logs with a tainted query value.
    code = 'const app=require("express");\napp.get("/log",(req,res)=>{ console.log("user=" + req.query.u); });'
    assert "LOG_INJECTION" in _types(code)


def test_logging_info_injection():
    code = 'def h(r):\n    logging.info("user " + r.form["u"])'
    assert "LOG_INJECTION" in _types(code)


def test_console_log_constant_clean():
    assert "LOG_INJECTION" not in _types('console.log("startup")')


def test_getattr_builtins_eval():
    code = 'def f(x):\n    g = getattr(__builtins__, "eval")\n    g(x)'
    assert "CMD_INJECTION" in _types(code) or "EVAL_USE" in _types(code)


def test_import_os_reflective():
    code = 'mod = __import__("os")\nmod.system(c)'
    assert "CMD_INJECTION" in _types(code)


def test_pem_private_key():
    code = "private = '-----BEGIN RSA PRIVATE KEY-----\\nMIIEowIBAA=='"
    assert "HARDCODED_CRED" in _types(code)


def test_status_200_fail_open():
    from code_shape.security.error_handling import find_error_handling_issues
    code = ("def a(r):\n    try:\n        check(r)\n"
            "    except Exception:\n        status = 200\n    return status")
    types = [i["type"] for i in find_error_handling_issues(code)]
    assert "FAILING_OPEN" in types


def test_reflective_negatives_clean():
    assert "CMD_INJECTION" not in _types('def f(o):\n    return getattr(o, "name")')
    assert "CMD_INJECTION" not in _types('m = __import__("json")')


def test_aliased_getattr_chain():
    # g = getattr; g(__builtins__, "eval") — alias-of-reflective bypass.
    code = 'def f(x):\n    g = getattr\n    g(__builtins__, "eval")(x)'
    assert "CMD_INJECTION" in _types(code) or "EVAL_USE" in _types(code)


def test_aliased_import_os():
    code = 'def f(c):\n    gi = __import__\n    os = gi("os")\n    os.system(c)'
    assert "CMD_INJECTION" in _types(code)


def test_aliased_reflective_negatives():
    # safe aliases of getattr/__import__ with benign args must stay clean.
    assert "CMD_INJECTION" not in _types('def f(o):\n    g = getattr\n    g(o, "name")')
    assert "CMD_INJECTION" not in _types('def f():\n    gi = __import__\n    m = gi("json")')


# ---- Shape-driven detection: catch obscure custom sink names by ROLE ----
def test_shape_invoke_process():
    code = "def f(cmd):\n    invoke_process(cmd)"
    assert "CMD_INJECTION" in _types(code)


def test_shape_query_users():
    code = "def f(v):\n    return query_users(v)"
    assert "SQL_INJECTION" in _types(code)


def test_shape_run_shell():
    code = "def f(u):\n    run_shell_command(u)"
    assert "CMD_INJECTION" in _types(code)


def test_shape_display_html():
    code = "def f(c):\n    display_html(c)"
    assert "XSS" in _types(code)


def test_shape_negative_no_taint():
    # A role-like call with NO tainted source must NOT flag (fp guard).
    assert "CMD_INJECTION" not in _types("def f():\n    invoke_process(query_text)")
    assert "SQL_INJECTION" not in _types('display_html("<b>static</b>")')


def test_shape_def_not_flagged_as_cmd():
    # Function DEFINITION whose name looks like a sink must not be a CMD.
    code = 'function executeSearch(query) {\n    return db.query("SELECT *" + query);\n}'
    assert "CMD_INJECTION" not in _types(code)  # only the real SQL fires
    assert "SQL_INJECTION" in _types(code)


# ---- Shape-driven cross-language (param = tainted entry point) ----
def test_shape_java_exec_command():
    code = "public void f(String c) { executeCommand(c); }"
    assert "CMD_INJECTION" in _types(code)


def test_shape_php_db_query():
    code = "function f($v){ return db_query($v); }"
    assert "SQL_INJECTION" in _types(code)


def test_shape_js_paint_content():
    code = "function f(x){ paint_content(x) }"
    assert "XSS" in _types(code)


def test_shape_internal_var_not_tainted():
    # A role-like call with an internally-computed (non-param, non-source) arg
    # must stay clean — the cross-language param logic must not over-taint.
    code = "def f():\n    x = compute()\n    return query_users(x)"
    assert "SQL_INJECTION" not in _types(code)


# ---- Cross-language WEAK_HASH additions ----
def test_cryptojs_md5():
    assert "WEAK_HASH" in _types("var h = CryptoJS.MD5(pw);")


def test_openssl_md5():
    assert "WEAK_HASH" in _types('$h = openssl::digest("md5", data);')


def test_java_messagedigest_md5():
    assert "WEAK_HASH" in _types('MessageDigest.getInstance("MD5")')


def test_weakhash_negatives():
    assert "WEAK_HASH" not in _types('$h = openssl::digest("sha256", data);')
    assert "WEAK_HASH" not in _types("count = md5_metric(x)")


# ---- find-more round 2: taint precision + more shape roles ----
def test_load_config_json_not_fp():
    # `json` inside a filename/string must NOT set taint -> load_config stays clean.
    code = "def f():\n    cfg = load_config('app.json')"
    assert "DESERIALIZATION" not in _types(code)


def test_shape_file_role_path_traversal():
    code = "def f(u):\n    read_path(u)"
    assert "PATH_TRAVERSAL" in _types(code)


def test_shape_unpack_deserialize():
    code = "def f(b):\n    unpack_data(b)"
    assert "DESERIALIZATION" in _types(code)


def test_shape_deserialize_constant_arg_clean():
    code = "def f():\n    cfg = load_config('settings.yml')"
    assert "DESERIALIZATION" not in _types(code)


def test_benign_open_db_clean():
    code = "def f():\n    return open_db(config)"
    assert "PATH_TRAVERSAL" not in _types(code)
    assert "CMD_INJECTION" not in _types(code)


def test_small_rsa_key():
    assert "WEAK_HASH" in _types("key = RSA.generate(512)")
    assert "WEAK_HASH" not in _types("key = RSA.generate(2048)")  # safe size
