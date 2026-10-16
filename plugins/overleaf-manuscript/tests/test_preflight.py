import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFLIGHT = HERE.parent / "skills" / "overleaf-manuscript" / "scripts" / "preflight.sh"

ENV = dict(os.environ,
           GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null",
           GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")

OVERLEAF_URL = "https://git.overleaf.com/abc123"
GITHUB_URL = "git@github.com:example-lab/manuscript.git"


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=str(cwd), env=ENV, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)
    if done.returncode:
        raise AssertionError("git %s failed: %s" % (" ".join(args), done.stderr))
    return done.stdout


def commit_file(repo, name, text):
    (Path(repo) / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", "change " + name)


def run_preflight(path, env=ENV, shell="bash"):
    done = subprocess.run([shell, str(PREFLIGHT), str(path)], env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)
    return done.returncode, done.stdout


def parse_fields(stdout):
    fields = {}
    for line in stdout.splitlines():
        key, sep, value = line.partition(": ")
        if sep and not line.startswith(" "):
            fields[key] = value
    return fields


def preflight(path):
    rc, stdout = run_preflight(path)
    return rc, parse_fields(stdout)


class Preflight(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_clone(self, configured_url, work_name="work"):
        """Return (seed, work). work is a clone whose origin URL reads as configured_url."""
        bare = self.tmp / "remote.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(bare))
        seed = self.tmp / "seed"
        git(self.tmp, "clone", "-q", str(bare), str(seed))
        git(seed, "checkout", "-q", "-b", "main")
        commit_file(seed, "main.tex", "\\documentclass{article}\n")
        git(seed, "push", "-q", "origin", "main")
        work = self.tmp / work_name
        git(self.tmp, "clone", "-q", str(bare), str(work))
        git(work, "config", "url.%s.insteadOf" % bare, configured_url)
        git(work, "remote", "set-url", "origin", configured_url)
        return seed, work

    def test_folder_without_git(self):
        rc, f = preflight(self.tmp)
        self.assertEqual((rc, f["mode"]), (0, "no-git"))
        self.assertIn("Overleaf has synced", f["action"])

    def test_overleaf_remote(self):
        _, work = self.make_clone(OVERLEAF_URL)
        self.assertEqual(preflight(work)[1]["mode"], "overleaf-git")

    def test_github_remote(self):
        _, work = self.make_clone(GITHUB_URL)
        self.assertEqual(preflight(work)[1]["mode"], "github-linked")

    def test_other_remote_asks_the_author(self):
        _, work = self.make_clone("https://example.com/x.git")
        f = preflight(work)[1]
        self.assertEqual(f["mode"], "other")
        self.assertIn("Ask the author", f["action"])

    def test_up_to_date(self):
        _, work = self.make_clone(GITHUB_URL)
        f = preflight(work)[1]
        self.assertEqual((f["behind"], f["ahead"], f["dirty"]), ("0", "0", "0"))
        self.assertTrue(f["action"].startswith("up to date"))

    def test_behind_and_clean_says_pull(self):
        seed, work = self.make_clone(GITHUB_URL)
        commit_file(seed, "results.tex", "new\n")
        git(seed, "push", "-q", "origin", "main")
        f = preflight(work)[1]
        self.assertEqual((f["fetch"], f["behind"], f["ahead"]), ("ok (origin)", "1", "0"))
        self.assertEqual(f["action"], "run git pull --ff-only")

    def test_diverged_says_stop(self):
        seed, work = self.make_clone(GITHUB_URL)
        commit_file(seed, "results.tex", "remote\n")
        git(seed, "push", "-q", "origin", "main")
        commit_file(work, "methods.tex", "local\n")
        f = preflight(work)[1]
        self.assertEqual((f["behind"], f["ahead"]), ("1", "1"))
        self.assertTrue(f["action"].startswith("stop and ask"))

    def test_tracked_change_blocks_pull(self):
        seed, work = self.make_clone(GITHUB_URL)
        commit_file(seed, "results.tex", "remote\n")
        git(seed, "push", "-q", "origin", "main")
        (work / "main.tex").write_text("edited\n", encoding="utf-8")
        f = preflight(work)[1]
        self.assertEqual((f["dirty"], f["behind"]), ("1", "1"))
        self.assertTrue(f["action"].startswith("stop and ask"))

    def test_untracked_file_does_not_block_pull(self):
        seed, work = self.make_clone(GITHUB_URL)
        commit_file(seed, "results.tex", "remote\n")
        git(seed, "push", "-q", "origin", "main")
        (work / "main.log").write_text("build log\n", encoding="utf-8")
        f = preflight(work)[1]
        self.assertEqual((f["dirty"], f["untracked"]), ("0", "1"))
        self.assertEqual(f["action"], "run git pull --ff-only")

    def test_failed_fetch_is_reported(self):
        _, work = self.make_clone(GITHUB_URL)
        shutil.rmtree(str(self.tmp / "remote.git"))
        rc, stdout = run_preflight(work)
        f = parse_fields(stdout)
        self.assertTrue(f["fetch"].startswith("failed"))
        self.assertEqual(stdout.splitlines()[-1],
                         "action: stop and ask. The fetch failed, so the counts may be stale.")

    def test_path_with_spaces_and_parentheses(self):
        _, work = self.make_clone(OVERLEAF_URL, work_name="Dropbox (CZ Biohub) copy")
        rc, f = preflight(work)
        self.assertEqual((rc, f["mode"], f["behind"]), (0, "overleaf-git", "0"))

    def test_detached_head_says_so_and_stops(self):
        _, work = self.make_clone(GITHUB_URL)
        git(work, "checkout", "-q", "--detach")
        f = preflight(work)[1]
        self.assertEqual(f["branch"], "(detached HEAD)")
        self.assertEqual(f["upstream"], "none")
        self.assertEqual(f["action"], "stop and ask. HEAD is detached; check out a branch first.")

    def test_branch_without_upstream_asks_which_branch_overleaf_tracks(self):
        _, work = self.make_clone(GITHUB_URL)
        git(work, "checkout", "-q", "-b", "scratch")
        f = preflight(work)[1]
        self.assertEqual((f["branch"], f["upstream"], f["fetch"]), ("scratch", "none", "ok (origin)"))
        self.assertTrue(f["action"].startswith("no upstream branch"))

    def add_second_remote(self, work, name="overleaf"):
        """Add a bare remote that main tracks. Return a clone of it, for a co-author's push."""
        second = self.tmp / (name + ".git")
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(second))
        git(work, "remote", "add", name, str(second))
        git(work, "push", "-q", name, "main")
        git(work, "branch", "--set-upstream-to=%s/main" % name, "main")
        other = self.tmp / ("coauthor-" + name)
        git(self.tmp, "clone", "-q", str(second), str(other))
        return other

    def test_upstream_on_a_second_remote_is_fetched(self):
        _, work = self.make_clone(GITHUB_URL)
        coauthor = self.add_second_remote(work)
        commit_file(coauthor, "results.tex", "co-author\n")
        git(coauthor, "push", "-q", "origin", "main")
        f = preflight(work)[1]
        self.assertEqual((f["fetch"], f["upstream"], f["behind"], f["ahead"]),
                         ("ok (overleaf)", "overleaf/main", "1", "0"))
        self.assertEqual(f["action"], "run git pull --ff-only")

    def test_failed_fetch_of_a_second_remote_names_that_remote(self):
        _, work = self.make_clone(GITHUB_URL)
        self.add_second_remote(work)
        shutil.rmtree(str(self.tmp / "overleaf.git"))
        rc, stdout = run_preflight(work)
        f = parse_fields(stdout)
        self.assertTrue(f["fetch"].startswith("failed (overleaf:"), f["fetch"])
        self.assertEqual(stdout.splitlines()[-1],
                         "action: stop and ask. The fetch failed, so the counts may be stale.")

    def test_unpushed_commits_are_reported_when_up_to_date(self):
        _, work = self.make_clone(GITHUB_URL)
        f = preflight(work)[1]
        self.assertEqual(f["action"], "up to date. Edit only after approval.")
        commit_file(work, "methods.tex", "local\n")
        f = preflight(work)[1]
        self.assertEqual((f["behind"], f["ahead"]), ("0", "1"))
        self.assertEqual(f["action"],
                         "up to date. Edit only after approval. 1 local commit is not pushed.")
        commit_file(work, "intro.tex", "local\n")
        self.assertEqual(preflight(work)[1]["action"],
                         "up to date. Edit only after approval. 2 local commits are not pushed.")

    def test_cdpath_does_not_print_the_folder(self):
        _, work = self.make_clone(OVERLEAF_URL, work_name="found-by-cdpath")
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        env = dict(ENV, CDPATH=str(self.tmp))
        done = subprocess.run(["bash", str(PREFLIGHT), "found-by-cdpath"], cwd=str(elsewhere), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("repo: "), done.stdout)
        self.assertEqual(parse_fields(done.stdout)["mode"], "overleaf-git")

    def test_folder_name_that_starts_with_a_dash(self):
        _, work = self.make_clone(OVERLEAF_URL, work_name="-dashed")
        done = subprocess.run(["bash", str(PREFLIGHT), "-dashed"], cwd=str(self.tmp), env=ENV,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(parse_fields(done.stdout)["mode"], "overleaf-git")

    def fake_ssh(self):
        """Write a stand-in for ssh. It records its arguments and exits with an error."""
        log = self.tmp / "ssh-args.txt"
        script = self.tmp / "fake_ssh.sh"
        script.write_text("#!/bin/sh\necho \"$@\" >> '%s'\nexit 255\n" % log, encoding="utf-8")
        script.chmod(0o755)
        return script, log

    def test_ssh_fetch_runs_in_batch_mode_so_a_passphrase_prompt_cannot_hang(self):
        _, work = self.make_clone(GITHUB_URL)
        git(work, "remote", "set-url", "origin", "ssh://git@github.com/example-lab/manuscript.git")
        script, log = self.fake_ssh()
        rc, stdout = run_preflight(work, env=dict(ENV, GIT_SSH_COMMAND=str(script)))
        self.assertIn("BatchMode=yes", log.read_text(encoding="utf-8"))
        self.assertTrue(parse_fields(stdout)["fetch"].startswith("failed"))
        self.assertEqual(stdout.splitlines()[-1],
                         "action: stop and ask. The fetch failed, so the counts may be stale.")

    def test_batch_mode_keeps_the_ssh_command_from_git_config(self):
        _, work = self.make_clone(GITHUB_URL)
        git(work, "remote", "set-url", "origin", "ssh://git@github.com/example-lab/manuscript.git")
        script, log = self.fake_ssh()
        git(work, "config", "core.sshCommand", str(script))
        env = {k: v for k, v in ENV.items() if k != "GIT_SSH_COMMAND"}
        run_preflight(work, env=env)
        self.assertIn("BatchMode=yes", log.read_text(encoding="utf-8"))

    def test_fetch_works_without_a_timeout_command(self):
        seed, work = self.make_clone(GITHUB_URL)
        commit_file(seed, "results.tex", "remote\n")
        git(seed, "push", "-q", "origin", "main")
        bindir = self.tmp / "bin"
        bindir.mkdir()
        for tool in ("git", "sh", "bash", "wc", "tr", "head", "sed", "grep", "cat"):
            found = shutil.which(tool)
            self.assertIsNotNone(found, tool + " is not installed")
            os.symlink(found, str(bindir / tool))
        self.assertIsNone(shutil.which("timeout", path=str(bindir)))
        self.assertIsNone(shutil.which("gtimeout", path=str(bindir)))
        bash = shutil.which("bash")
        env = dict(ENV, PATH=str(bindir))
        rc, stdout = run_preflight(work, env=env, shell=bash)
        f = parse_fields(stdout)
        self.assertEqual((f["fetch"], f["behind"]), ("ok (origin)", "1"))
        self.assertEqual(f["action"], "run git pull --ff-only")

    def test_remote_url_is_redacted(self):
        _, work = self.make_clone("https://git:olp_SECRETTOKEN123@git.overleaf.com/abc123")
        rc, stdout = run_preflight(work)
        f = parse_fields(stdout)
        self.assertNotIn("SECRETTOKEN123", stdout)
        self.assertEqual((rc, f["mode"], f["remote"]),
                         (0, "overleaf-git", "https://git.overleaf.com/abc123"))

    def test_remote_url_is_redacted_when_the_password_holds_an_at_sign(self):
        _, work = self.make_clone("https://git:pa@ss_SECRETTAIL@git.overleaf.com/abc123")
        rc, stdout = run_preflight(work)
        f = parse_fields(stdout)
        self.assertNotIn("SECRETTAIL", stdout)
        self.assertEqual((rc, f["mode"], f["remote"]),
                         (0, "overleaf-git", "https://git.overleaf.com/abc123"))


if __name__ == "__main__":
    unittest.main()
