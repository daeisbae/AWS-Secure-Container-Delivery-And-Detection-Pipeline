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


def _safe_http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def _scanner(run: dict[str, Any]) -> tuple[str, str | None]:
    driver = _mapping(_mapping(run.get("tool")).get("driver"))
    name = driver.get("name")
    scanner_name = str(name) if isinstance(name, (str, int)) else "Unknown scanner"
    version = driver.get("semanticVersion") or driver.get("version")
    scanner_version = str(version) if isinstance(version, (str, int)) else None
    return scanner_name, scanner_version


def _finding_html(result: dict[str, Any], rule: dict[str, Any], number: int) -> str:
    rule_id_value = result.get("ruleId") or rule.get("id") or "Unidentified rule"
    rule_id = html.escape(str(rule_id_value), quote=True)
    severity = _severity(result, rule)
    severity_label = html.escape(severity.upper(), quote=True)
    message = _message_text(result.get("message")) or "No finding description provided."
    location = _location(result)
    details = (
        _message_text(rule.get("fullDescription"))
        or _message_text(rule.get("help"))
        or _message_text(rule.get("shortDescription"))
    )
    help_url = _safe_http_url(rule.get("helpUri"))

    reference = ""
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

    return f"""
        <li class="finding">
          <div class="finding-heading">
            <span class="severity severity-{severity}">{severity_label}</span>
            <code>{rule_id}</code>
          </div>
          <div class="location">{html.escape(location, quote=True)}</div>
          <div class="message">{html.escape(message, quote=True)}</div>
          <div class="finding-footer">
            <span>Finding {number}</span>
            {reference}
          </div>
          {detail_block}
        </li>"""


def render_html(sarif: dict[str, Any], title: str, source_name: str) -> str:
    if sarif.get("version") != "2.1.0":
        raise ValueError("Expected a SARIF 2.1.0 document")

    runs = [run for run in _sequence(sarif.get("runs")) if isinstance(run, dict)]
    total_findings = sum(len(_sequence(run.get("results"))) for run in runs)
    escaped_title = html.escape(title, quote=True)
    escaped_source = html.escape(source_name, quote=True)
    finding_word = "finding" if total_findings == 1 else "findings"

    run_sections: list[str] = []
    for run_number, run in enumerate(runs, start=1):
        scanner_name, scanner_version = _scanner(run)
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
        count_badges = "".join(
            f'<span class="count"><strong>{count}</strong> '
            f'{html.escape(level.upper(), quote=True)}</span>'
            for level, count in sorted(counts.items())
        )
        version_html = (
            f'<span class="scanner-version">Version '
            f'{html.escape(scanner_version, quote=True)}</span>'
            if scanner_version
            else ""
        )
        findings_html = "".join(
            _finding_html(result, rule, finding_number)
            for finding_number, (result, rule) in enumerate(resolved, start=1)
        )
        if not findings_html:
            findings_html = '<p class="empty">No findings were reported.</p>'
        else:
            findings_html = f'<ol class="findings">{findings_html}</ol>'

        run_sections.append(
            f"""
      <section class="run" aria-labelledby="run-{run_number}">
        <header class="run-header">
          <div>
            <p class="eyebrow">Scanner run {run_number}</p>
            <h2 id="run-{run_number}">{html.escape(scanner_name, quote=True)}</h2>
            {version_html}
          </div>
          <div class="counts">{count_badges}</div>
        </header>
        {findings_html}
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
    :root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #0b1020; color: #e8edf7; line-height: 1.5; }}
    main {{ width: min(1100px, calc(100% - 2rem)); margin: 0 auto; padding: 2.5rem 0 4rem; }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: .5rem; font-size: clamp(1.8rem, 4vw, 2.6rem); }}
    h2 {{ margin-bottom: .2rem; }}
    code {{ overflow-wrap: anywhere; color: #dce7ff; }}
    a {{ color: #8db8ff; }}
    .subtitle, .scanner-version, .location, .finding-footer {{ color: #aebbd3; }}
    .summary {{ display: flex; gap: .75rem; flex-wrap: wrap; margin: 1.5rem 0 2rem; }}
    .summary-item, .count {{ border: 1px solid #34415f; border-radius: 999px; padding: .35rem .7rem; }}
    .run {{ margin-top: 1.25rem; border: 1px solid #2d3954; border-radius: 14px; background: #11182a; overflow: hidden; }}
    .run-header {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1.25rem; border-bottom: 1px solid #2d3954; }}
    .eyebrow {{ margin-bottom: .15rem; color: #8db8ff; font-size: .78rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
    .counts {{ display: flex; gap: .5rem; flex-wrap: wrap; justify-content: flex-end; }}
    .findings {{ list-style: none; padding: 1rem; margin: 0; display: grid; gap: .8rem; }}
    .finding {{ border: 1px solid #34415f; border-radius: 10px; padding: 1rem; background: #0e1526; }}
    .finding-heading, .finding-footer {{ display: flex; align-items: center; justify-content: space-between; gap: .75rem; }}
    .severity {{ flex: 0 0 auto; border-radius: 999px; padding: .2rem .55rem; color: #fff; font-size: .72rem; font-weight: 800; letter-spacing: .04em; }}
    .severity-critical, .severity-error {{ background: #b42318; }}
    .severity-high {{ background: #c2410c; }}
    .severity-medium, .severity-warning {{ background: #a15c00; }}
    .severity-low, .severity-note {{ background: #176b3a; }}
    .severity-unknown, .severity-none {{ background: #526078; }}
    .location {{ margin-top: .7rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .86rem; overflow-wrap: anywhere; }}
    .message, .details-text {{ margin-top: .75rem; white-space: pre-wrap; overflow-wrap: anywhere; }}
    .finding-footer {{ margin-top: .9rem; font-size: .86rem; }}
    details {{ margin-top: .8rem; }}
    summary {{ cursor: pointer; color: #cbd7ed; }}
    .empty {{ margin: 0; padding: 1.25rem; color: #aebbd3; }}
    @media (max-width: 650px) {{
      .run-header, .finding-heading, .finding-footer {{ align-items: flex-start; flex-direction: column; }}
      .counts {{ justify-content: flex-start; }}
    }}
    @media print {{
      body {{ background: #fff; color: #111827; }}
      main {{ width: 100%; padding: 0; }}
      .run, .finding {{ background: #fff; border-color: #cbd5e1; break-inside: avoid; }}
      code, a {{ color: #1e3a8a; }}
      .subtitle, .scanner-version, .location, .finding-footer, .empty {{ color: #475569; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{escaped_title}</h1>
      <p class="subtitle">Human-readable export of <code>{escaped_source}</code></p>
      <div class="summary" aria-label="Report summary">
        <span class="summary-item"><strong>{total_findings}</strong> {finding_word}</span>
        <span class="summary-item"><strong>{len(runs)}</strong> scanner run{'s' if len(runs) != 1 else ''}</span>
        <span class="summary-item">SARIF 2.1.0</span>
      </div>
    </header>
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
        render_html(sarif, title=title, source_name=input_path.name),
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
