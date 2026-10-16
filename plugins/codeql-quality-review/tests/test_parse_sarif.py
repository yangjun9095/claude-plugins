"""Tests for scripts/parse_sarif.py.

Run from the plugin directory:
    python3 -B -m unittest discover -s tests

Each test builds a tiny SARIF file with made-up paths and rule ids in a temporary directory.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PLUGIN, "scripts", "parse_sarif.py")

# An ASCII locale. PYTHONCOERCECLOCALE=0 and PYTHONUTF8=0 keep the child on ASCII for
# Python 3.7 and later. Python 3.6 ignores them. The child never inherits PYTHONIOENCODING.
ASCII_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}


def make_sarif(message):
    return {"version": "2.1.0", "runs": [{"results": [
        {"ruleId": "py/rule-a", "message": {"text": message},
         "locations": [{"physicalLocation": {
             "artifactLocation": {"uri": "src/a.py"}, "region": {"startLine": 3}}}]},
    ]}]}


class ParseSarifInAnAsciiLocale(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def run_on(self, sarif):
        path = os.path.join(self.folder, "quality.sarif")
        with open(path, "wb") as handle:
            handle.write(json.dumps(sarif, ensure_ascii=False).encode("utf-8"))
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        env.update(ASCII_LOCALE)
        proc = subprocess.Popen([sys.executable, "-B", SCRIPT, path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        out, err = proc.communicate()
        return proc.returncode, out.decode("utf-8"), err.decode("utf-8")

    def test_ascii_sarif_file(self):
        code, out, err = self.run_on(make_sarif("Message A."))
        self.assertEqual(code, 0, err)
        self.assertIn("STANDARD TOTAL: 1", out)
        self.assertIn("py/rule-a", out)
        self.assertIn("src/a.py:3", out)

    def test_sarif_file_with_a_non_ascii_message(self):
        code, out, err = self.run_on(make_sarif("Name ‘x’ is not used: café."))
        self.assertEqual(code, 0, err)
        self.assertIn("STANDARD TOTAL: 1", out)
        self.assertIn("Name ‘x’ is not used: café.", out)


if __name__ == "__main__":
    unittest.main()
