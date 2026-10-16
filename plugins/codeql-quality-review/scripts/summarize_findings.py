#!/usr/bin/env python3
"""Summarize Code Quality findings from the GitHub REST API.

Usage:
    python3 summarize_findings.py [findings.json]
    gh api --paginate "repos/OWNER/REPO/code-quality/findings?state=open&per_page=100" \\
        | python3 summarize_findings.py

The script reads the file you name, or standard input when you name none.
It accepts three shapes of input:
    one JSON array of findings,
    several JSON arrays one after another (the output of gh api --paginate),
    one array of arrays (the output of gh api --paginate --slurp).

The output has the total, the counts by severity, category and rule, the ten files
with the most findings, and one line per finding grouped by rule.

Exit code 0 means success. Exit code 2 means unreadable or non-finding input.
The script uses only the Python standard library and runs on Python 3.6.
"""
import json
import sys

NAME = "summarize_findings.py"
USAGE = "usage: %s [findings.json]" % NAME
JSON_SPACE = " \t\r\n"
SEVERITY_ORDER = ["error", "warning", "note", "none"]
TOP_FILES = 10
JSON_KINDS = {dict: "object", list: "array", str: "string", int: "number",
              float: "number", bool: "boolean", type(None): "null"}


class InputError(Exception):
    """The input cannot be read or does not hold a list of findings."""


def read_text(path):
    """Read the file at path, or standard input when path is None. Return text."""
    if path is None:
        stream = getattr(sys.stdin, "buffer", None)
        data = stream.read() if stream is not None else sys.stdin.read().encode("utf-8")
    else:
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as error:
            raise InputError("cannot read %s: %s" % (path, error.strerror or error))
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError("the input is not UTF-8 text")


def decode_values(text):
    """Return every JSON value in the text. The values can follow one another."""
    decoder = json.JSONDecoder()
    values = []
    pos = 0
    while True:
        while pos < len(text) and text[pos] in JSON_SPACE:
            pos += 1
        if pos >= len(text):
            return values
        try:
            value, pos = decoder.raw_decode(text, pos)
        except ValueError as error:
            position = getattr(error, "pos", pos)
            raise InputError("invalid JSON at character %d: %s" % (position, getattr(error, "msg", error)))
        values.append(value)


def check_finding(item, number):
    """Raise InputError unless item looks like a finding. Only the rule id is required."""
    rule = item.get("rule") if isinstance(item, dict) else None
    if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
        raise InputError("item %d is not a finding (it has no rule id)" % number)


def load_findings(text):
    """Return the list of findings in the text."""
    values = decode_values(text)
    if not values:
        raise InputError("no JSON found in the input")
    findings = []
    for value in values:
        if not isinstance(value, list):
            kind = JSON_KINDS.get(type(value), "value")
            hint = ""
            if isinstance(value, dict) and isinstance(value.get("message"), str):
                hint = " (message: %s)" % " ".join(value["message"].split())[:80]
            raise InputError("expected a list of findings but got a JSON %s%s" % (kind, hint))
        for item in value:
            for finding in (item if isinstance(item, list) else [item]):
                check_finding(finding, len(findings) + 1)
                findings.append(finding)
    return findings


def ranked(counts):
    """Sort (name, count) pairs by count, highest first, then by name."""
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))


def tally(findings, getter):
    counts = {}
    for finding in findings:
        key = getter(finding)
        counts[key] = counts.get(key, 0) + 1
    return counts


def severity_key(name):
    """Order the known severities from most to least severe, then the rest by name."""
    if name in SEVERITY_ORDER:
        return (SEVERITY_ORDER.index(name), name)
    return (len(SEVERITY_ORDER), name)


def rule_of(finding):
    return finding["rule"]


def path_of(finding):
    location = finding.get("location")
    return (location.get("path") if isinstance(location, dict) else None) or "(no path)"


def line_of(finding):
    location = finding.get("location")
    line = location.get("start_line") if isinstance(location, dict) else None
    return line if isinstance(line, int) else None


def message_of(finding):
    """Return the message text on one line. Fall back to the rule title."""
    message = finding.get("message")
    text = message.get("text") if isinstance(message, dict) else message
    return " ".join(str(text or rule_of(finding).get("title") or "").split())


def summarize(findings):
    """Return the summary text for a list of findings."""
    out = ["Total findings: %d" % len(findings)]
    if not findings:
        return "\n".join(out) + "\n"

    out += ["", "By severity:"]
    severities = tally(findings, lambda f: rule_of(f).get("severity") or "unknown")
    for name, count in sorted(severities.items(), key=lambda pair: severity_key(pair[0])):
        out.append("  %d  %s" % (count, name))

    out += ["", "By category:"]
    for name, count in ranked(tally(findings, lambda f: rule_of(f).get("category") or "unknown")):
        out.append("  %d  %s" % (count, name))

    titles = {}
    for finding in findings:
        rule = rule_of(finding)
        if rule.get("title") and rule["id"] not in titles:
            titles[rule["id"]] = " ".join(str(rule["title"]).split())
    by_rule = ranked(tally(findings, lambda f: rule_of(f)["id"]))

    out += ["", "By rule:"]
    for rule_id, count in by_rule:
        out.append(("  %d  %s  %s" % (count, rule_id, titles.get(rule_id, ""))).rstrip())

    out += ["", "Top files:"]
    for path, count in ranked(tally(findings, path_of))[:TOP_FILES]:
        out.append("  %d  %s" % (count, path))

    out += ["", "Findings by rule:"]
    for rule_id, count in by_rule:
        header = "## %s (%d)" % (rule_id, count)
        out += ["", header + (": " + titles[rule_id] if rule_id in titles else "")]
        members = [f for f in findings if rule_of(f)["id"] == rule_id]
        for finding in sorted(members, key=lambda f: (path_of(f), line_of(f) or 0)):
            line = line_of(finding)
            text = "%s:%s: %s: %s" % (
                path_of(finding), line if line is not None else "?", rule_id, message_of(finding))
            out.append(text.rstrip())
    return "\n".join(out) + "\n"


def write_text(stream, text):
    """Write UTF-8 text. A plain ASCII locale must not break a finding message."""
    if hasattr(stream, "buffer"):
        stream.flush()
        stream.buffer.write(text.encode("utf-8"))
        stream.buffer.flush()
    else:
        stream.write(text)


def main(argv):
    if len(argv) > 1 or (argv and argv[0].startswith("-") and argv[0] != "-"):
        write_text(sys.stderr, USAGE + "\n")
        return 2
    path = argv[0] if argv and argv[0] != "-" else None
    try:
        summary = summarize(load_findings(read_text(path)))
    except InputError as error:
        write_text(sys.stderr, "%s: %s\n" % (NAME, error))
        return 2
    write_text(sys.stdout, summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
