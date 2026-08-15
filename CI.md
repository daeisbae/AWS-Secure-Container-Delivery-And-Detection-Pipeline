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

