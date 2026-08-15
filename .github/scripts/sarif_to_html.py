#!/usr/bin/env python3
"""Render a self-contained, human-readable HTML report from SARIF 2.1.0."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit


KNOWN_SEVERITIES = ("critical", "high", "medium", "low", "unknown")
KNOWN_LEVELS = ("error", "warning", "note", "none")
SEVERITY_ORDER = (
    "critical",
    "error",
    "high",
    "medium",
    "warning",
    "low",
    "note",
    "none",
    "unknown",
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _message_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    message = _mapping(value)
    for key in ("text", "markdown"):
        text = message.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def _rules_for_run(
    run: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    driver = _mapping(_mapping(run.get("tool")).get("driver"))
    rules = [
        rule for rule in _sequence(driver.get("rules")) if isinstance(rule, dict)
    ]
    rules_by_id = {
        str(rule["id"]): rule
        for rule in rules
        if isinstance(rule.get("id"), (str, int))
    }
    return rules, rules_by_id


def _rule_for_result(
    result: dict[str, Any],
    rules: list[dict[str, Any]],
    rules_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rule_id = result.get("ruleId")
    if isinstance(rule_id, (str, int)) and str(rule_id) in rules_by_id:
        return rules_by_id[str(rule_id)]

    rule_index = result.get("ruleIndex")
    if isinstance(rule_index, int) and 0 <= rule_index < len(rules):
        return rules[rule_index]
    return {}


def _severity(result: dict[str, Any], rule: dict[str, Any]) -> str:
    properties = _mapping(rule.get("properties"))
    tags = {
        str(tag).strip().lower()
        for tag in _sequence(properties.get("tags"))
        if isinstance(tag, (str, int))
    }
    for severity in KNOWN_SEVERITIES:
        if severity in tags:
            return severity

    result_level = result.get("level")
    if isinstance(result_level, str) and result_level.lower() in KNOWN_LEVELS:
        return result_level.lower()

    default_level = _mapping(rule.get("defaultConfiguration")).get("level")
    if isinstance(default_level, str) and default_level.lower() in KNOWN_LEVELS:
        return default_level.lower()
    return "unknown"


def _location(result: dict[str, Any]) -> str:
    locations = _sequence(result.get("locations"))
    if not locations or not isinstance(locations[0], dict):
        return "No location reported"

    physical = _mapping(locations[0].get("physicalLocation"))
    artifact = _mapping(physical.get("artifactLocation"))
    region = _mapping(physical.get("region"))
    uri = artifact.get("uri")
    label = str(uri) if isinstance(uri, (str, int)) else "No file reported"

    line = region.get("startLine")
    column = region.get("startColumn")
    if isinstance(line, int):
        label += f":{line}"
        if isinstance(column, int):
            label += f":{column}"
    return label


def _snippet(result: dict[str, Any]) -> str:
    locations = _sequence(result.get("locations"))
    if not locations or not isinstance(locations[0], dict):
        return ""

    physical = _mapping(locations[0].get("physicalLocation"))
    region = _mapping(physical.get("region"))
    return _message_text(region.get("snippet"))


def _safe_http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def _finding_html(result: dict[str, Any], rule: dict[str, Any], number: int) -> str:
    rule_id_value = result.get("ruleId") or rule.get("id") or "Unidentified rule"
    rule_id = html.escape(str(rule_id_value), quote=True)
    severity = _severity(result, rule)
    severity_label = html.escape(severity.upper(), quote=True)
    message = _message_text(result.get("message")) or "No finding description provided."
    location = _location(result)
    snippet = _snippet(result)
    details = (
        _message_text(rule.get("fullDescription"))
        or _message_text(rule.get("help"))
        or _message_text(rule.get("shortDescription"))
    )
    help_url = _safe_http_url(rule.get("helpUri"))

    reference = '<span class="muted">-</span>'
    if help_url:
        escaped_url = html.escape(help_url, quote=True)
        reference = (
            f'<a href="{escaped_url}" target="_blank" rel="noopener noreferrer">'
            "Open reference</a>"
        )

    detail_block = ""
    if details and details != message:
        detail_block = (
            "<details><summary>Rule details</summary>"
            f'<div class="details-text">{html.escape(details, quote=True)}</div>'
            "</details>"
        )

    snippet_block = ""
    if snippet:
        snippet_block = (
            '<pre class="code-snippet"><code>'
            f"{html.escape(snippet, quote=True)}"
            "</code></pre>"
        )

    return f"""
        <tr class="finding-row severity-{severity}">
          <td class="finding-number">{number}</td>
          <td class="severity-cell">{severity_label}</td>
          <td><code class="rule-id">{rule_id}</code></td>
          <td>
            <code class="location">{html.escape(location, quote=True)}</code>
            {snippet_block}
          </td>
          <td>
            <div class="message">{html.escape(message, quote=True)}</div>
            {detail_block}
          </td>
          <td class="reference">{reference}</td>
        </tr>"""


def render_html(sarif: dict[str, Any], title: str) -> str:
    if sarif.get("version") != "2.1.0":
        raise ValueError("Expected a SARIF 2.1.0 document")

    runs = [run for run in _sequence(sarif.get("runs")) if isinstance(run, dict)]
    escaped_title = html.escape(title, quote=True)

    run_sections: list[str] = []
    for run in runs:
        results = [
            result
            for result in _sequence(run.get("results"))
            if isinstance(result, dict)
        ]
        rules, rules_by_id = _rules_for_run(run)
        resolved = [
            (result, _rule_for_result(result, rules, rules_by_id)) for result in results
        ]
        counts = Counter(_severity(result, rule) for result, rule in resolved)
        count_rows = "".join(
            f'<tr class="severity-{level}">'
            f'<th scope="row" class="severity-cell">'
            f'{html.escape(level.upper(), quote=True)}</th>'
            f'<td>{counts[level]}</td></tr>'
            for level in SEVERITY_ORDER
            if counts[level]
        )
        findings_html = "".join(
            _finding_html(result, rule, finding_number)
            for finding_number, (result, rule) in enumerate(resolved, start=1)
        )
        if not findings_html:
            findings_html = (
                '<tr><td class="empty" colspan="6">'
                "No findings were reported.</td></tr>"
            )

        run_sections.append(
            f"""
      <section class="run">
        <h3>Severity summary</h3>
        <div class="table-scroll compact-table">
          <table class="severity-summary">
            <caption>Finding counts by severity</caption>
            <thead>
              <tr><th scope="col">Severity</th><th scope="col">Count</th></tr>
            </thead>
            <tbody>{count_rows or '<tr><td colspan="2">No findings</td></tr>'}</tbody>
          </table>
        </div>
        <h3>Findings</h3>
        <div class="table-scroll">
          <table class="findings-table">
            <caption>Findings</caption>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Severity</th>
                <th scope="col">Rule ID</th>
                <th scope="col">Location</th>
                <th scope="col">Finding</th>
                <th scope="col">Reference</th>
              </tr>
            </thead>
            <tbody>{findings_html}</tbody>
          </table>
        </div>
      </section>"""
        )

    if not run_sections:
        run_sections.append(
            '<section class="run"><p class="empty">No scanner runs were reported.</p></section>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
  <title>{escaped_title}</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, Helvetica, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #fff; color: #222; font-size: 14px; line-height: 1.45; }}
    main {{ width: min(1400px, calc(100% - 2rem)); margin: 0 auto; padding: 2rem 0 3rem; }}
    h1, h3, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 2rem; text-align: center; font-size: 2rem; }}
    h3 {{ margin: 1.5rem 0 .45rem; font-size: 1rem; }}
    code {{ font-family: Menlo, Consolas, monospace; overflow-wrap: anywhere; }}
    a {{ color: #0b57a3; }}
    .run > h3:first-child {{ margin-top: 0; }}
    .run + .run {{ margin-top: 2rem; padding-top: 2rem; border-top: 2px solid #b7b7b7; }}
    .table-scroll {{ width: 100%; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; border-spacing: 0; }}
    caption {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }}
    th, td {{ border: 1px solid #b7b7b7; padding: .55rem .65rem; text-align: left; vertical-align: top; }}
    thead th {{ background: #666; color: #fff; font-weight: 700; white-space: nowrap; }}
    .compact-table {{ max-width: 420px; margin: 0 auto; }}
    .severity-summary th, .severity-summary td {{ width: 50%; }}
    .severity-summary td {{ background: #f4f4f4; text-align: center; font-weight: 700; }}
    .findings-table {{ min-width: 980px; }}
    .findings-table td {{ background: #f2f2f2; }}
    .finding-number {{ width: 3rem; text-align: center; }}
    .severity-cell {{ width: 7rem; color: #fff; font-weight: 700; text-align: center; white-space: nowrap; }}
    .severity-critical .severity-cell, .severity-error .severity-cell {{ background: #d92d20; }}
    .severity-high .severity-cell {{ background: #ed7d31; }}
    .severity-medium .severity-cell, .severity-warning .severity-cell {{ background: #f2c94c; color: #222; }}
    .severity-low .severity-cell, .severity-note .severity-cell {{ background: #5aa647; }}
    .severity-unknown .severity-cell, .severity-none .severity-cell {{ background: #6b7280; }}
    .finding-row.severity-critical td, .finding-row.severity-error td {{ background: #fdebea; }}
    .finding-row.severity-high td {{ background: #fff0e6; }}
    .finding-row.severity-medium td, .finding-row.severity-warning td {{ background: #fff8d9; }}
    .finding-row.severity-low td, .finding-row.severity-note td {{ background: #edf7e9; }}
    .finding-row.severity-unknown td, .finding-row.severity-none td {{ background: #f0f1f3; }}
    .finding-row.severity-critical .severity-cell, .finding-row.severity-error .severity-cell {{ background: #d92d20; color: #fff; }}
    .finding-row.severity-high .severity-cell {{ background: #ed7d31; color: #fff; }}
    .finding-row.severity-medium .severity-cell, .finding-row.severity-warning .severity-cell {{ background: #f2c94c; color: #222; }}
    .finding-row.severity-low .severity-cell, .finding-row.severity-note .severity-cell {{ background: #5aa647; color: #fff; }}
    .finding-row.severity-unknown .severity-cell, .finding-row.severity-none .severity-cell {{ background: #6b7280; color: #fff; }}
    .rule-id, .location {{ font-size: .86rem; }}
    .message, .details-text {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
    .code-snippet {{ max-width: 34rem; margin: .55rem 0 0; padding: .5rem; overflow-x: auto; border: 1px solid #c6c6c6; background: #fff; white-space: pre-wrap; }}
    .reference {{ text-align: center; white-space: nowrap; }}
    .muted {{ color: #666; }}
    details {{ margin-top: .55rem; }}
    summary {{ cursor: pointer; color: #444; font-weight: 700; }}
    .empty {{ padding: 1rem; color: #555; text-align: center; }}
    @media (max-width: 700px) {{
      main {{ width: min(100% - 1rem, 1400px); padding-top: 1rem; }}
      h1 {{ font-size: 1.55rem; }}
    }}
    @media print {{
      main {{ width: 100%; padding: 0; }}
      body, .severity-cell, thead th {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
      .table-scroll {{ overflow: visible; }}
      .findings-table {{ min-width: 0; font-size: 10px; }}
      tr {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>{escaped_title}</h1>
    {''.join(run_sections)}
  </main>
</body>
</html>
"""


def convert(input_path: Path, output_path: Path, title: str) -> None:
    with input_path.open(encoding="utf-8") as source:
        sarif = json.load(source)
    if not isinstance(sarif, dict):
        raise ValueError("Expected the SARIF document to be a JSON object")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_html(sarif, title=title),
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a self-contained HTML report from SARIF 2.1.0."
    )
    parser.add_argument("input", type=Path, help="Input SARIF file")
    parser.add_argument("output", type=Path, help="Output HTML file")
    parser.add_argument(
        "--title", default="Security scan report", help="Title shown in the report"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    convert(args.input, args.output, args.title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
