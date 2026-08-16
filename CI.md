# First run before remediation

![](images/github-actions-security-gates-failed.png)

## SAST: login SQL injection

![](images/opengrep-sql-injection-finding.png)

### Cause

`_load_login_record()` inserts username directly into SQL text and sends that string to db cursor. Because the value becomes part of the query syntax, a crafted username can alter the WHERE SQL syntax.

### Fix

![](images/sql-injection-parameterized-query-fix.png)

The remediation use the f-string query the `:username` placeholder. `connection.execute()` receives the unfiltered input (username) in a separate parameter, the SQLAlchemy function will filter it before execution.

![](images/sqlalchemy-bound-parameter-example.png)

This is the [SQLAlchemy docs](https://docs.sqlalchemy.org/en/21/core/sqlelement.html) referenced above.

## DAST: missing browser security headers

![](images/zap-missing-security-headers.png)

### Cause

The /search route escapes the query before writing it into HTML, but the application does not add browser security headers. ZAP found no Content Security Policy and no anti-clickjacking policy header. Informational and Low alerts remain visible without blocking delivery, while Medium and High alerts reject the production candidate.

### Fix

Add response middleware so every route receives Content-Security-Policy, `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff`. A reasonable policy for this page is `default-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` as it only allows application interaction itself without any legacy plugin.
