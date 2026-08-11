# AWS Secure Container Delivery Pipeline

This lab uses one imaginary vulnerable FastAPI e-commerce application to implement security pipeline.

![Pipeline architecture](docs/architecture-security-headers.png)

## Workflow

1. Install the test dependencies and run pytest.
2. Build the container.
3. Run Trivy against the final image for Critical OS and Python package findings.
4. Run the local Opengrep rule against the login implementation.
5. Start that same image on an internal Docker network and run an OWASP ZAP scan.
6. Generate a CycloneDX SBOM with Trivy.
7. Package the image only if every security gate passes.
8. For an approved main branch run, obtain short-lived AWS credentials through GitHub OIDC, push the same image to ECR, sign and verify its digest with Cosign, and update ECS.

## Experiments

### Experiment 1: Dependencies and Vulnerable Container

We are expecting to find the vulnerable packages / container images below using Trivy

| Layer | Installed package | Expected CVE |
| --- | --- | --- |
| Alpine | sqlite-libs 3.48.0-r0 | CVE-2025-3277 |
| Python | Authlib 1.6.8 | CVE-2026-27962 |
| Python | SQLAlchemy 1.2.17 | CVE-2019-7164 |
| Python | SQLAlchemy 1.2.17 | CVE-2019-7548 |

### Experiment 2: SAST for login SQL Injection

The `/login` route reaches `_load_login_record()` in `app/store.py`. That function inserts `credentials.username` into an SQL string before passing it to `connection.execute()`.

The workflow downloads Opengrep, and scans the file with `opengrep/experiment2-sql-injection.yml`.

### Experiment 3: DAST for Security Header Misconfiguration

The `/search` route HTML encodes the submitted product query but omits browser security headers. (A lot of times, developers do not know about this) We will run the pinned OWASP ZAP passive baseline scan against `/search?q=keyboard`.
