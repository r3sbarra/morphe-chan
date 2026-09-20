#!/usr/bin/env python
"""taxonomy.py — Authoritative CWE/CVE taxonomy, OWASP mapping, and security tagging.

Maps code-shape vulnerability types to official MITRE CWE IDs, OWASP Top 10 (2021),
representative CVE identifiers, default severity ratings, and multi-dimensional security tags.

Dependency-free (stdlib only).
"""
from typing import Any, Dict, List, Optional

# ── Master Taxonomy Dictionary ──────────────────────────────────────────────
VULN_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "SQL_INJECTION": {
        "cwe": "CWE-89",
        "cwe_title": "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')",
        "owasp": "A03:2021-Injection",
        "severity": "CRITICAL",
        "impact": "data-exfiltration",
        "cve_examples": ["CVE-2019-19781", "CVE-2023-34362", "CVE-2014-3704"],
        "tags": ["injection", "database", "owasp:a03:2021", "cwe:89", "data-exfiltration", "data-tampering"],
        "description": "Untrusted input concatenated or interpolated directly into SQL statements without parameter binding.",
    },
    "CMD_INJECTION": {
        "cwe": "CWE-78",
        "cwe_title": "Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')",
        "owasp": "A03:2021-Injection",
        "severity": "CRITICAL",
        "impact": "rce",
        "cve_examples": ["CVE-2019-15107", "CVE-2021-41773", "CVE-2014-6271"],
        "tags": ["injection", "os-command", "rce", "owasp:a03:2021", "cwe:78", "system-compromise"],
        "description": "User input passed to operating system command execution functions or shell interpreters.",
    },
    "EVAL_USE": {
        "cwe": "CWE-95",
        "cwe_title": "Improper Neutralization of Directives in Dynamically Evaluated Code ('Eval Injection')",
        "owasp": "A03:2021-Injection",
        "severity": "CRITICAL",
        "impact": "rce",
        "cve_examples": ["CVE-2018-7600", "CVE-2022-22965"],
        "tags": ["code-injection", "rce", "dynamic-eval", "owasp:a03:2021", "cwe:95"],
        "description": "Execution of dynamic code strings via eval(), exec(), or script engines containing untrusted input.",
    },
    "OGNL_INJECTION": {
        "cwe": "CWE-917",
        "cwe_title": "Improper Neutralization of Special Elements used in an Expression Language Statement ('Expression Language Injection')",
        "owasp": "A03:2021-Injection",
        "severity": "CRITICAL",
        "impact": "rce",
        "cve_examples": ["CVE-2017-5638", "CVE-2018-11776"],
        "tags": ["injection", "expression-language", "rce", "owasp:a03:2021", "cwe:917"],
        "description": "Untrusted data evaluated as Object-Graph Navigation Language (OGNL) expressions leading to RCE.",
    },
    "JNDI_INJECTION": {
        "cwe": "CWE-944",
        "cwe_title": "Insecure Storage of Sensitive Information in Java Naming and Directory Interface (JNDI)",
        "owasp": "A03:2021-Injection",
        "severity": "CRITICAL",
        "impact": "rce",
        "cve_examples": ["CVE-2021-44228", "CVE-2022-22965"],
        "tags": ["injection", "jndi", "rce", "remote-class-loading", "owasp:a03:2021", "cwe:944"],
        "description": "Untrusted input passed to JNDI lookups allowing LDAP/RMI remote codebase loading.",
    },
    "TEMPLATE_INJECTION": {
        "cwe": "CWE-1336",
        "cwe_title": "Improper Neutralization of Special Elements Used in a Template Engine",
        "owasp": "A03:2021-Injection",
        "severity": "HIGH",
        "impact": "rce",
        "cve_examples": ["CVE-2019-8341", "CVE-2020-3580"],
        "tags": ["injection", "template", "ssti", "rce", "owasp:a03:2021", "cwe:1336"],
        "description": "Server-Side Template Injection (SSTI) embedding untrusted input directly into template source.",
    },
    "PATH_TRAVERSAL": {
        "cwe": "CWE-22",
        "cwe_title": "Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')",
        "owasp": "A01:2021-Broken Access Control",
        "severity": "HIGH",
        "impact": "arbitrary-file-read-write",
        "cve_examples": ["CVE-2020-3452", "CVE-2021-41773", "CVE-2021-42013"],
        "tags": ["file-system", "path-traversal", "owasp:a01:2021", "cwe:22", "data-leak"],
        "description": "Filesystem operations using paths constructed from untrusted input without canonicalization or bounds checking.",
    },
    "XSS": {
        "cwe": "CWE-79",
        "cwe_title": "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')",
        "owasp": "A03:2021-Injection",
        "severity": "HIGH",
        "impact": "client-compromise",
        "cve_examples": ["CVE-2020-11022", "CVE-2021-21315"],
        "tags": ["web", "xss", "client-side", "owasp:a03:2021", "cwe:79", "session-hijack"],
        "description": "Untrusted input rendered directly into HTML or DOM sinks without proper context-aware sanitization.",
    },
    "DESERIALIZATION": {
        "cwe": "CWE-502",
        "cwe_title": "Deserialization of Untrusted Data",
        "owasp": "A08:2021-Software and Data Integrity Failures",
        "severity": "CRITICAL",
        "impact": "rce",
        "cve_examples": ["CVE-2023-46604", "CVE-2015-4854", "CVE-2017-7525"],
        "tags": ["deserialization", "rce", "object-injection", "owasp:a08:2021", "cwe:502"],
        "description": "Unsafe deserialization of untrusted byte streams or serialized object formats (pickle, yaml, Java ObjectInputStream).",
    },
    "BUFFER_OVERFLOW": {
        "cwe": "CWE-120",
        "cwe_title": "Buffer Copy without Checking Size of Input ('Classic Buffer Overflow')",
        "owasp": "A06:2021-Vulnerable and Outdated Components",
        "severity": "CRITICAL",
        "impact": "rce",
        "cve_examples": ["CVE-2017-0144", "CVE-2014-0160", "CVE-2015-5477"],
        "tags": ["memory-safety", "buffer-overflow", "bounds", "cwe:120", "cwe:787"],
        "description": "Unchecked array indexing, buffer allocation, or memory copying without size or bounds validation.",
    },
    "HARDCODED_CRED": {
        "cwe": "CWE-798",
        "cwe_title": "Use of Hard-coded Credentials",
        "owasp": "A07:2021-Identification and Authentication Failures",
        "severity": "HIGH",
        "impact": "auth-bypass",
        "cve_examples": ["CVE-2020-2509", "CVE-2021-22926"],
        "tags": ["secrets", "credentials", "authentication", "owasp:a07:2021", "cwe:798"],
        "description": "Sensitive credentials, passwords, private keys, or API tokens stored directly in source code.",
    },
    "SSRF": {
        "cwe": "CWE-918",
        "cwe_title": "Server-Side Request Forgery (SSRF)",
        "owasp": "A10:2021-Server-Side Request Forgery (SSRF)",
        "severity": "HIGH",
        "impact": "internal-network-access",
        "cve_examples": ["CVE-2021-26855", "CVE-2020-11651"],
        "tags": ["network", "ssrf", "internal-recon", "owasp:a10:2021", "cwe:918"],
        "description": "Server makes outbound network requests to URLs or hosts supplied by untrusted users without allowlist validation.",
    },
    "XXE": {
        "cwe": "CWE-611",
        "cwe_title": "Improper Restriction of XML External Entity Reference",
        "owasp": "A05:2021-Security Misconfiguration",
        "severity": "HIGH",
        "impact": "data-leak",
        "cve_examples": ["CVE-2014-3529", "CVE-2019-14862"],
        "tags": ["xml", "xxe", "file-disclosure", "owasp:a05:2021", "cwe:611"],
        "description": "XML parser configured to resolve external entities or DTDs, enabling local file disclosure and SSRF.",
    },
    "LDAP_INJECTION": {
        "cwe": "CWE-90",
        "cwe_title": "Improper Neutralization of Special Elements used in an LDAP Query ('LDAP Injection')",
        "owasp": "A03:2021-Injection",
        "severity": "HIGH",
        "impact": "auth-bypass",
        "cve_examples": ["CVE-2008-2083"],
        "tags": ["injection", "ldap", "authentication", "owasp:a03:2021", "cwe:90"],
        "description": "Untrusted input concatenated into LDAP search filters without escaping special characters.",
    },
    "HEADER_INJECTION": {
        "cwe": "CWE-113",
        "cwe_title": "Improper Neutralization of CRLF Sequences in HTTP Headers ('HTTP Request/Response Splitting')",
        "owasp": "A03:2021-Injection",
        "severity": "MEDIUM",
        "impact": "cache-poisoning",
        "cve_examples": ["CVE-2016-4977", "CVE-2019-11358"],
        "tags": ["http", "crlf", "headers", "splitting", "cwe:113"],
        "description": "Untrusted data set directly in HTTP headers without filtering newline characters (CRLF).",
    },
    "LOG_INJECTION": {
        "cwe": "CWE-117",
        "cwe_title": "Improper Output Handling for Logs",
        "owasp": "A09:2021-Security Logging and Monitoring Failures",
        "severity": "LOW",
        "impact": "log-forgery",
        "cve_examples": ["CVE-2020-10673"],
        "tags": ["logging", "forgery", "crlf", "owasp:a09:2021", "cwe:117"],
        "description": "Writing unescaped user input containing newlines into log files, facilitating log forging or deception.",
    },
    "OPEN_REDIRECT": {
        "cwe": "CWE-601",
        "cwe_title": "URL Redirection to Untrusted Site ('Open Redirect')",
        "owasp": "A01:2021-Broken Access Control",
        "severity": "MEDIUM",
        "impact": "phishing",
        "cve_examples": ["CVE-2021-27582"],
        "tags": ["redirect", "phishing", "web", "owasp:a01:2021", "cwe:601"],
        "description": "Application redirects users to arbitrary target URLs specified by untrusted input parameters.",
    },
    "INSECURE_RANDOM": {
        "cwe": "CWE-330",
        "cwe_title": "Use of Insufficiently Random Values",
        "owasp": "A02:2021-Cryptographic Failures",
        "severity": "MEDIUM",
        "impact": "token-prediction",
        "cve_examples": ["CVE-2008-0166", "CVE-2013-6387"],
        "tags": ["crypto", "randomness", "prng", "owasp:a02:2021", "cwe:330"],
        "description": "Using pseudo-random generators (e.g. random.random) for security-sensitive tokens or keys.",
    },
    "WEAK_HASH": {
        "cwe": "CWE-327",
        "cwe_title": "Use of a Broken or Risky Cryptographic Algorithm",
        "owasp": "A02:2021-Cryptographic Failures",
        "severity": "MEDIUM",
        "impact": "collision-hash-reversal",
        "cve_examples": ["CVE-2004-2761"],
        "tags": ["crypto", "hash", "md5", "sha1", "owasp:a02:2021", "cwe:327"],
        "description": "Using deprecated or collision-prone cryptographic hash functions such as MD5 or SHA-1 for security.",
    },
    "CSRF": {
        "cwe": "CWE-352",
        "cwe_title": "Cross-Site Request Forgery (CSRF)",
        "owasp": "A01:2021-Broken Access Control",
        "severity": "HIGH",
        "impact": "unauthorized-action",
        "cve_examples": ["CVE-2020-11023"],
        "tags": ["csrf", "session", "web", "owasp:a01:2021", "cwe:352"],
        "description": "State-changing actions performed without anti-CSRF token verification.",
    },
    "IDOR": {
        "cwe": "CWE-639",
        "cwe_title": "Authorization Bypass Through User-Controlled Key",
        "owasp": "A01:2021-Broken Access Control",
        "severity": "HIGH",
        "impact": "unauthorized-data-access",
        "cve_examples": ["CVE-2023-22515"],
        "tags": ["idor", "authorization", "access-control", "owasp:a01:2021", "cwe:639"],
        "description": "Direct access to objects or records using user-supplied IDs without verifying ownership or authorization.",
    },
    "FAILING_OPEN": {
        "cwe": "CWE-636",
        "cwe_title": "Not Failing Securely (Failing Open)",
        "owasp": "A10:2025-Mishandling of Exceptional Conditions",
        "severity": "CRITICAL",
        "impact": "authorization-bypass",
        "cve_examples": [],
        "tags": ["error-handling", "fail-open", "authz", "owasp:a10:2025", "cwe:636"],
        "description": "On an exceptional condition the app defaults to an insecure state (grants access/returns success) instead of denying — fails OPEN.",
    },
    "SWALLOWED": {
        "cwe": "CWE-390",
        "cwe_title": "Detection of Error Condition Without Action",
        "owasp": "A10:2025-Mishandling of Exceptional Conditions",
        "severity": "MEDIUM",
        "impact": "logic-error",
        "cve_examples": [],
        "tags": ["error-handling", "swallowed-exception", "owasp:a10:2025", "cwe:390"],
        "description": "An exception is caught but no recovery action is taken; the caller proceeds as if the operation succeeded.",
    },
    "NULL_DEREF": {
        "cwe": "CWE-476",
        "cwe_title": "NULL Pointer Dereference",
        "owasp": "A10:2025-Mishandling of Exceptional Conditions",
        "severity": "MEDIUM",
        "impact": "crash-dos",
        "cve_examples": ["CVE-2007-5000"],
        "tags": ["error-handling", "null-deref", "owasp:a10:2025", "cwe:476"],
        "description": "Dereferencing the result of a fallible call (e.g. .first()/.find()) without checking for None / not-found.",
    },
    "ERROR_LEAK": {
        "cwe": "CWE-209",
        "cwe_title": "Generation of Error Message Containing Sensitive Information",
        "owasp": "A10:2025-Mishandling of Exceptional Conditions",
        "severity": "HIGH",
        "impact": "information-disclosure",
        "cve_examples": ["CVE-2019-5418", "CVE-2017-12149"],
        "tags": ["error-handling", "info-leak", "owasp:a10:2025", "cwe:209"],
        "description": "An error/exception message includes sensitive data (passwords, tokens, secrets, raw SQL, stack traces).",
    },
    "MISSING_PARAM": {
        "cwe": "CWE-234",
        "cwe_title": "Failure to Handle Missing Parameter",
        "owasp": "A10:2025-Mishandling of Exceptional Conditions",
        "severity": "LOW",
        "impact": "logic-error",
        "cve_examples": [],
        "tags": ["error-handling", "missing-param", "owasp:a10:2025", "cwe:234"],
        "description": "Accessing a user-supplied dict/request key without first checking it is present (KeyError / missing-param logic error).",
    },
}

# Fallback taxonomy for unmapped types
DEFAULT_TAXONOMY: Dict[str, Any] = {
    "cwe": "CWE-699",
    "cwe_title": "Software Development Weakness",
    "owasp": "A00:2021-Unknown",
    "severity": "MEDIUM",
    "impact": "unknown",
    "cve_examples": [],
    "tags": ["general-weakness"],
    "description": "Potential security vulnerability detected during code analysis.",
}

# Concrete, actionable remediation guidance per vulnerability type. Surfaced on
# each enriched finding (a way to USE the findings: not just flag, but fix).
REMEDIATION_GUIDE: Dict[str, str] = {
    "SQL_INJECTION": "Use parameterized queries / prepared statements (e.g. db.execute('... WHERE id = ?', (uid,))) or an ORM. Never concatenate/interpolate untrusted input into SQL.",
    "CMD_INJECTION": "Avoid shell invocation with untrusted input. Use argument lists (subprocess.run([cmd, arg])) instead of shell=True/string, or shlex.quote; prefer safer APIs and an allowlist.",
    "EVAL_USE": "Remove eval()/exec()/compile() of untrusted input. Use a safe parser/domain logic or an allowlisted interpreter; never eval request data.",
    "OGNL_INJECTION": "Do not evaluate user input as OGNL/expression-language. Use a parameter-safe templating engine and block arbitrary property access.",
    "JNDI_INJECTION": "Disable remote JNDI/class loading (e.g. com.sun.jndi.rmi.object.trustURLCodebase=false), allowlist LDAP servers, upgrade Log4j to >=2.17.0.",
    "TEMPLATE_INJECTION": "Do not render untrusted input through template engines (render_template_string). Use static templates + a sandboxed/autoescaped engine; never pass user data as template source.",
    "XSS": "Encode/escape all output for the context (text/attribute/JS). Use textContent not innerHTML, add a CSP header, and sanitize HTML.",
    "PATH_TRAVERSAL": "Validate/normalize user paths against an allowlist base (os.path.realpath + check prefix), reject .. and absolute paths; never concatenate input into file paths.",
    "SSRF": "Restrict outbound requests to an allowlist of hosts/ports, block private/link-local IP ranges, and validate the URL scheme; never pass raw user URLs to fetch/requests/urlopen.",
    "XXE": "Disable external entity resolution (e.g. disallow-doctype-decl, resolve_entities=False); do not pass user-controlled XML to XXE-enabled parsers.",
    "LDAP_INJECTION": "Escape LDAP special chars or use encoded filter APIs; never embed user input directly in LDAP search/bind filters.",
    "DESERIALIZATION": "Never deserialize untrusted input. Use safe formats (JSON with schema validation) and an allowlist/checksum for pickle/yaml.",
    "HARDCODED_CRED": "Move secrets to a secrets manager / env vars; rotate any leaked credential and revoke API keys; never hardcode passwords or tokens.",
    "WEAK_HASH": "Replace MD5/SHA1 with a strong password hash (argon2/bcrypt/scrypt/PBKDF2); never use MD5/SHA1 for security.",
    "INSECURE_RANDOM": "Use a cryptographically secure RNG (secrets / System.Security.Cryptography) for tokens, salts, and security-sensitive values.",
    "HEADER_INJECTION": "Validate/encode header values and reject CR/LF; use framework response helpers that forbid header injection.",
    "LOG_INJECTION": "Log structured fields and encode/escape user-controlled values (CR/LF, brackets); never log raw untrusted input.",
    "OPEN_REDIRECT": "Validate redirect destinations against an allowlist (is_safe_url) and only redirect to relative/known hosts, never raw user URLs.",
    "CSRF": "Add CSRF tokens to state-changing requests, validate Origin/Referer, and use SameSite cookies.",
    "IDOR": "Enforce object-level authorization: verify the current user owns / is permitted to access the requested resource id, not just the id param.",
    "BUFFER_OVERFLOW": "Validate array index bounds before access (0 <= i < len) and avoid unchecked variable-length indexing; use safe containers.",
    "ERROR_LEAK": "Return generic error messages to clients; log full details server-side only; redact secrets/SQL/stack traces from responses.",
    "NULL_DEREF": "Check for None/not-found before dereferencing fallible calls (.first()/.find()/.get()); use optionals/defaults.",
    "SWALLOWED": "Handle exceptions explicitly (log + recover) instead of silently swallowing; propagate or record the failure.",
    "FAILING_OPEN": "On auth/validation failure, fail closed (deny) and log; never grant access on exception or missing check.",
    "MISSING_PARAM": "Check that required user-supplied keys/params are present before use; validate types and ranges.",
    "JNDI_LOOKUP": "See JNDI_INJECTION: disable remote codebase loading and upgrade vulnerable libraries.",
}


def get_taxonomy(vuln_type: str) -> Dict[str, Any]:
    """Retrieve official CWE, OWASP, severity, and tagging metadata for a vulnerability type."""
    return VULN_TAXONOMY.get(vuln_type.upper(), DEFAULT_TAXONOMY.copy())


def enrich_vulnerability(vuln: Dict[str, Any], code: Optional[str] = None) -> Dict[str, Any]:
    """Enrich a vulnerability finding dictionary with taxonomy and exploitability metadata."""
    vtype = vuln.get("type", "UNKNOWN")
    tax = get_taxonomy(vtype)
    
    enriched = dict(vuln)
    enriched["cwe"] = tax["cwe"]
    enriched["cwe_id"] = tax["cwe"]
    enriched["cwe_title"] = tax["cwe_title"]
    enriched["owasp"] = tax["owasp"]
    enriched["description"] = tax.get("description", "")
    enriched["cve_examples"] = list(tax["cve_examples"])
    enriched["remediation"] = REMEDIATION_GUIDE.get(
        vtype.upper(), "Review this code path: untrusted data should be validated, parameterized, and encoded for its context.")
    
    # Combined tags: base taxonomy tags + contextual tags
    tags = set(tax["tags"])
    if enriched.get("source"):
        tags.add(f"source:{enriched['source']}")
    if enriched.get("shape_dimension"):
        tags.add(f"shape:{enriched['shape_dimension']}")
    enriched["tags"] = sorted(tags)

    # Compute exploitability if code snippet is available
    if code:
        from code_shape.security.exploitability import exploitability_score
        exp = exploitability_score(code, vtype)
        enriched["exploitability"] = exp
        # Dynamic severity adjustments based on exploitability
        if exp["score"] >= 0.8:
            enriched["severity"] = "CRITICAL"
        elif exp["score"] >= 0.6:
            enriched["severity"] = "HIGH"
        elif exp["score"] >= 0.4:
            enriched["severity"] = "MEDIUM"
        else:
            enriched["severity"] = tax["severity"]
    else:
        enriched["severity"] = tax["severity"]
        enriched["exploitability"] = {
            "score": 0.5,
            "label": tax["severity"],
            "impact": 0.5,
            "public_taint": 0.0,
            "mitigated": 1.0,
            "directness": 0.5,
        }

    return enriched
