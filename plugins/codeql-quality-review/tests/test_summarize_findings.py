"""Tests for scripts/summarize_findings.py.

Run from the plugin directory:
    python3 -B -m unittest discover -s tests

The sample findings follow the schema of the GitHub REST endpoint
GET /repos/{owner}/{repo}/code-quality/findings. All paths and rule ids are made up.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PLUGIN, "scripts", "summarize_findings.py")


def make_finding(number=1, rule_id="py/rule-a", title="Title A", severity="warning",
                 category="maintainability", path="src/a.py", start_line=10,
                 message="Message A.", state="open"):
    """Build one finding. Pass None for start_line, number or message to leave the field out."""
    location = {"path": path, "start_column": 1, "end_line": 11, "end_column": 5}
    if start_line is not None:
        location["start_line"] = start_line
    finding = {
        "state": state,
        "url": "https://example.invalid/findings/%s" % number,
        "rule": {"id": rule_id, "title": title, "description": "Description.",
                 "severity": severity, "category": category},
        "location": location,
        "created_at": "2026-01-01T00:00:00Z",
    }
    if number is not None:
        finding["number"] = number
    if message is not None:
        finding["message"] = {"text": message, "markdown": message}
    return finding


def sample_findings():
    """Three findings: two for py/rule-a (one file each), one for py/rule-b."""
    return [
        make_finding(1, "py/rule-a", "Title A", "warning", "maintainability", "src/a.py", 10, "Message A1."),
        make_finding(2, "py/rule-a", "Title A", "warning", "maintainability", "src/b.py", 20, "Message A2."),
        make_finding(3, "py/rule-b", "Title B", "error", "reliability", "src/a.py", 5, "Message B1."),
    ]


# An ASCII locale. PYTHONCOERCECLOCALE=0 and PYTHONUTF8=0 keep the child on ASCII for
# Python 3.7 and later, where the C locale would otherwise switch to UTF-8. Python 3.6 ignores them.
ASCII_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}


def run_script(args=(), stdin_text=None, env=None, script=SCRIPT):
    """Run a script in a child process. Return (exit code, stdout, stderr) as text.

    Each argument can be text or bytes. The child never inherits PYTHONIOENCODING or
    PYTHONUTF8, because either one hides an encoding bug.
    """
    child_env = dict(os.environ)
    for name in ("PYTHONIOENCODING", "PYTHONUTF8"):
        child_env.pop(name, None)
    if env:
        child_env.update(env)
    command = [os.fsencode(sys.executable), b"-B", os.fsencode(script)]
    command += [arg if isinstance(arg, bytes) else arg.encode("utf-8") for arg in args]
    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=child_env)
    if stdin_text is None:
        data = b""
    elif isinstance(stdin_text, bytes):
        data = stdin_text
    else:
        data = stdin_text.encode("utf-8")
    out, err = proc.communicate(data)
    return proc.returncode, out.decode("utf-8"), err.decode("utf-8")


def count_lines(output, name):
    """Return the counts printed as '  N  name' lines, keyed by name."""
    found = {}
    for match in re.finditer(r"^\s+(\d+)\s+(\S+)", output, re.MULTILINE):
        found[match.group(2)] = int(match.group(1))
    return found.get(name)


class SingleArray(unittest.TestCase):
    def test_summary_of_one_array_on_stdin(self):
        code, out, err = run_script(stdin_text=json.dumps(sample_findings()))
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("Total findings: 3", out)
        self.assertEqual(count_lines(out, "warning"), 2)
        self.assertEqual(count_lines(out, "error"), 1)
        self.assertEqual(count_lines(out, "maintainability"), 2)
        self.assertEqual(count_lines(out, "reliability"), 1)
        self.assertRegex(out, r"(?m)^\s+2\s+py/rule-a\s+warning\s+maintainability\s+Title A$")
        self.assertRegex(out, r"(?m)^\s+1\s+py/rule-b\s+error\s+reliability\s+Title B$")

    def test_file_counts_use_the_path(self):
        code, out, _ = run_script(stdin_text=json.dumps(sample_findings()))
        self.assertEqual(code, 0)
        self.assertEqual(count_lines(out, "src/a.py"), 2)
        self.assertEqual(count_lines(out, "src/b.py"), 1)

    def test_one_line_per_finding_grouped_by_rule_and_sorted_by_path(self):
        # The input lists src/b.py:20 before src/a.py:10, so only a sort puts them in path order.
        findings = [sample_findings()[1], sample_findings()[0], sample_findings()[2]]
        code, out, _ = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0)
        lines = out.splitlines()
        a1 = lines.index("#1 src/a.py:10: py/rule-a: Message A1.")
        a2 = lines.index("#2 src/b.py:20: py/rule-a: Message A2.")
        b1 = lines.index("#3 src/a.py:5: py/rule-b: Message B1.")
        self.assertEqual(a2, a1 + 1)
        self.assertLess(a2, b1)

    def test_findings_in_one_file_are_listed_by_line_number(self):
        # The input lists line 30 before line 4 in one file, so only a numeric sort by line orders them.
        findings = [make_finding(1, path="src/a.py", start_line=30, message="Late."),
                    make_finding(2, path="src/a.py", start_line=4, message="Early.")]
        code, out, err = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        early = lines.index("#2 src/a.py:4: py/rule-a: Early.")
        late = lines.index("#1 src/a.py:30: py/rule-a: Late.")
        self.assertEqual(late, early + 1)

    def test_finding_without_a_number_prints_a_question_mark(self):
        findings = [make_finding(number=None, message="No number here.")]
        code, out, err = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0, err)
        self.assertIn("#? src/a.py:10: py/rule-a: No number here.", out.splitlines())

    def test_message_falls_back_to_the_rule_title(self):
        findings = [make_finding(1, message=""), make_finding(2, path="src/b.py", message=None)]
        code, out, err = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertIn("#1 src/a.py:10: py/rule-a: Title A", lines)
        self.assertIn("#2 src/b.py:10: py/rule-a: Title A", lines)

    def test_file_path_argument(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(sample_findings(), handle)
        try:
            code, out, err = run_script([handle.name])
        finally:
            os.unlink(handle.name)
        self.assertEqual(code, 0, err)
        self.assertIn("Total findings: 3", out)

    def test_empty_array(self):
        code, out, err = run_script(stdin_text="[]")
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertEqual(out, "Total findings: 0\n")


class PaginatedShapes(unittest.TestCase):
    """Some gh versions print one JSON array per page. With --slurp gh prints an array of arrays."""

    def setUp(self):
        findings = sample_findings()
        self.page_one = findings[:2]
        self.page_two = findings[2:]

    def assert_same_as_single_array(self, stdin_text):
        _, expected, _ = run_script(stdin_text=json.dumps(sample_findings()))
        code, out, err = run_script(stdin_text=stdin_text)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, expected)

    def test_concatenated_arrays_on_one_line(self):
        self.assert_same_as_single_array(json.dumps(self.page_one) + json.dumps(self.page_two))

    def test_concatenated_arrays_on_separate_lines(self):
        self.assert_same_as_single_array(
            json.dumps(self.page_one, indent=2) + "\n" + json.dumps(self.page_two, indent=2) + "\n")

    def test_slurped_array_of_arrays(self):
        self.assert_same_as_single_array(json.dumps([self.page_one, self.page_two]))

    def test_concatenated_arrays_including_an_empty_page(self):
        self.assert_same_as_single_array(json.dumps(sample_findings()) + "\n[]\n")


class Ordering(unittest.TestCase):
    def test_severity_lists_the_most_severe_first_whatever_the_counts(self):
        findings = [
            make_finding(1, severity="note", path="src/a.py"),
            make_finding(2, severity="note", path="src/b.py"),
            make_finding(3, severity="warning", path="src/c.py"),
            make_finding(4, severity="error", path="src/d.py"),
        ]
        code, out, _ = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0)
        block = out.split("By severity:")[1].split("By category:")[0]
        self.assertEqual(re.findall(r"\d+\s+(\w+)", block), ["error", "warning", "note"])

    def test_only_the_ten_files_with_most_findings_are_listed(self):
        findings = []
        for index in range(12):
            for repeat in range(index + 1):
                findings.append(make_finding(len(findings) + 1, path="src/file%02d.py" % index))
        code, out, _ = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0)
        block = out.split("Top files:")[1].split("Findings by rule:")[0]
        listed = re.findall(r"\d+\s+(src/file\d+\.py)", block)
        self.assertEqual(listed[0], "src/file11.py")
        self.assertEqual(len(listed), 10)
        self.assertNotIn("src/file00.py", listed)
        self.assertNotIn("src/file01.py", listed)


class MissingOptionalFields(unittest.TestCase):
    def test_finding_without_start_line(self):
        findings = [make_finding(1, path="src/no_line.py", start_line=None, message="No line here.")]
        code, out, err = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0, err)
        self.assertIn("#1 src/no_line.py:?: py/rule-a: No line here.", out.splitlines())

    def test_finding_without_help_title_location_or_message(self):
        bare = {"number": 7, "state": "open", "rule": {"id": "py/rule-bare"}}
        code, out, err = run_script(stdin_text=json.dumps([bare, make_finding(2)]))
        self.assertEqual(code, 0, err)
        self.assertIn("Total findings: 2", out)
        severity_block = out.split("By severity:")[1].split("By category:")[0]
        category_block = out.split("By category:")[1].split("By rule:")[0]
        self.assertIn("  1  unknown", severity_block)
        self.assertIn("  1  unknown", category_block)
        self.assertIn("#7 (no path):?: py/rule-bare:", out.splitlines())
        self.assertRegex(out, r"(?m)^\s+1\s+py/rule-bare\s+\?\s+\?$")

    def test_message_with_a_newline_stays_on_one_line(self):
        findings = [make_finding(1, message="First line.\nSecond line.")]
        code, out, _ = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0)
        self.assertIn("#1 src/a.py:10: py/rule-a: First line. Second line.", out.splitlines())

    def test_non_ascii_message_in_a_plain_ascii_locale(self):
        findings = [make_finding(1, message="Name ‘x’ is not used: café.")]
        code, out, err = run_script(stdin_text=json.dumps(findings), env=ASCII_LOCALE)
        self.assertEqual(code, 0, err)
        self.assertIn("Name ‘x’ is not used: café.", out)

    def test_lone_surrogate_in_a_path_and_a_message(self):
        # json.dumps writes the lone surrogate as the ASCII escape \ud800.
        findings = [make_finding(1, path="src/bad\ud800.py", message="Bad \ud800 character.")]
        code, out, err = run_script(stdin_text=json.dumps(findings))
        self.assertEqual(code, 0, err)
        self.assertNotIn("Traceback", err)
        self.assertIn("#1 src/bad?.py:10: py/rule-a: Bad ? character.", out.splitlines())


class NonAsciiPathArgument(unittest.TestCase):
    def test_missing_file_with_a_non_ascii_name_exits_2_with_one_line(self):
        code, out, err = run_script([b"/nonexistent/caf\xc3\xa9.json"], env=ASCII_LOCALE)
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn("cannot read", err)
        self.assertNotIn("Traceback", err)

    def test_existing_file_with_a_non_ascii_name_is_read(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(os.fsencode(folder), b"caf\xc3\xa9.json")
        try:
            with open(path, "w") as handle:
                json.dump(sample_findings(), handle)
            code, out, err = run_script([path], env=ASCII_LOCALE)
        finally:
            os.unlink(path)
            os.rmdir(folder)
        self.assertEqual(code, 0, err)
        self.assertIn("Total findings: 3", out)


class BadInput(unittest.TestCase):
    """Bad input must give exit code 2, an empty stdout and a one-line message on stderr."""

    def assert_rejected(self, stdin_text=None, args=(), expect=""):
        code, out, err = run_script(args, stdin_text=stdin_text)
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn(expect, err)
        self.assertNotIn("Traceback", err)

    def test_invalid_json(self):
        self.assert_rejected("[{", expect="invalid JSON")

    def test_text_after_a_valid_array(self):
        self.assert_rejected("[] unexpected", expect="invalid JSON")

    def test_error_object_from_the_api(self):
        body = json.dumps({"message": "Not Found", "documentation_url": "https://example.invalid", "status": "404"})
        self.assert_rejected(body, expect="Not Found")

    def test_object_that_is_not_a_finding_list(self):
        self.assert_rejected(json.dumps({"total": 3}), expect="list of findings")

    def test_scalar_json(self):
        self.assert_rejected("42", expect="list of findings")

    def test_array_of_numbers(self):
        self.assert_rejected("[1, 2]", expect="not a finding")

    def test_array_of_objects_without_a_rule(self):
        self.assert_rejected(json.dumps([{"number": 1}]), expect="not a finding")

    def test_rule_that_is_a_string(self):
        self.assert_rejected(json.dumps([{"number": 1, "rule": "py/rule-a"}]), expect="not a finding")

    def test_slurped_input_with_one_bad_item(self):
        self.assert_rejected(json.dumps([sample_findings(), [5]]), expect="not a finding")

    def test_empty_input(self):
        self.assert_rejected("  \n", expect="no JSON")

    def test_bytes_that_are_not_utf8(self):
        self.assert_rejected(b"[\xff]", expect="UTF-8")

    def test_missing_file(self):
        self.assert_rejected(args=["/nonexistent/findings.json"], expect="cannot read")

    def test_two_file_arguments(self):
        self.assert_rejected(args=["one.json", "two.json"], expect="usage")

    def test_unknown_option(self):
        self.assert_rejected(args=["--bogus"], expect="usage")


if __name__ == "__main__":
    unittest.main()
