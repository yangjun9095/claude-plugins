#!/bin/sh
# Launcher contract tests. Run under BOTH dash and bash.
set -eu
# Absolute: the cwd-hardening tests below run the launcher from another directory.
ABD_BIN="$(cd "$(dirname "$0")/../bin" && pwd)/abd"
fail() { echo "FAIL: $1" >&2; exit 1; }

# 1. --version prints a version and exits 0
out=$("$ABD_BIN" --version) || fail "--version exited non-zero"
echo "$out" | grep -qE '^agent-board [0-9]+\.[0-9]+\.[0-9]+$' || fail "bad --version: $out"

# 2. hook subcommand exits 0 even with NO usable interpreter
out=$(ABD_PYTHON=/nonexistent/python PATH=/nonexistent "$ABD_BIN" hook session-start </dev/null 2>&1) \
  || fail "hook must exit 0 with no interpreter"
[ -z "$out" ] || fail "hook must print nothing when disabled, got: $out"

# 3. non-hook subcommand with no interpreter exits 127 with one stderr line
set +e
out=$(ABD_PYTHON=/nonexistent/python PATH=/nonexistent "$ABD_BIN" board 2>&1); rc=$?
set -e
[ "$rc" = "127" ] || fail "expected rc=127 with no interpreter, got $rc"
echo "$out" | grep -q 'no python' || fail "expected a 'no python' message, got: $out"

# 4. works when symlinked onto PATH (resolves its own root)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
ln -s "$(cd "$(dirname "$ABD_BIN")" && pwd)/abd" "$tmp/abd"
env -i PATH="$tmp:/usr/bin:/bin" "$tmp/abd" --version >/dev/null || fail "symlink install broken"

# 5. hook with working interpreter exits 0 with empty output (fail-open guarantee)
out=$("$ABD_BIN" hook session-start </dev/null 2>&1) || fail "hook with working interpreter must exit 0"
[ -z "$out" ] || fail "hook with working interpreter must print nothing, got: $out"

# --- cwd must never be executable code (sys.path[0] hardening) ---------------
# Both of these executed the caller's cwd before the -I probe and the runpy
# bootstrap landed. `rich.py` is a mundane filename; `agent_board/` is the
# tool's own package name, which any checkout of this repo has at its root.
cwd=$(mktemp -d); deg=''            # deg is set below; the trap reads it under set -u
trap 'rm -rf "$tmp" "$cwd" ${deg:+"$deg"}' EXIT

# 6. a cwd-local rich.py is NOT executed by the interpreter probe
cat > "$cwd/rich.py" <<'PY'
open("PWNED", "w").close()
PY
(cd "$cwd" && "$ABD_BIN" --version >/dev/null 2>&1) || fail "--version broke in a dir with rich.py"
[ ! -f "$cwd/PWNED" ] || fail "cwd-local rich.py was EXECUTED by the probe"

# 6b. ...not even via `abd hook`, which fires in whatever dir a session opens
rm -f "$cwd/PWNED"
(cd "$cwd" && "$ABD_BIN" hook session-start </dev/null >/dev/null 2>&1) || fail "hook must exit 0"
[ ! -f "$cwd/PWNED" ] || fail "cwd-local rich.py was EXECUTED by the hook probe"

# 7. a cwd-local agent_board/ does NOT shadow the real package
mkdir -p "$cwd/agent_board"
: > "$cwd/agent_board/__init__.py"
echo 'print("SHADOWED-BY-CWD")' > "$cwd/agent_board/__main__.py"
out=$(cd "$cwd" && "$ABD_BIN" --version 2>&1) || fail "--version exited non-zero under a shadowing cwd"
echo "$out" | grep -qE '^agent-board [0-9]+\.[0-9]+\.[0-9]+$' \
  || fail "cwd-local agent_board/ shadowed the real package: $out"

# --- readlink is external: a degraded PATH must not break the hook ----------
# Condition 4 covers symlink+full PATH and condition 2 covers degraded PATH
# alone; only BOTH together reach the readlink call.
deg=$(mktemp -d); ln -s "$(cd "$(dirname "$ABD_BIN")" && pwd)/abd" "$deg/abd"

# 8. symlinked onto PATH with no coreutils: hook still exits 0, silently
out=$(env -i PATH="$deg" "$deg/abd" hook session-start </dev/null 2>&1) \
  || fail "symlink + degraded PATH must still exit 0 for hook"
[ -z "$out" ] || fail "hook must print nothing on a degraded PATH, got: $out"

# 9. same shape, non-hook verb: a named error, never 'readlink: not found'
set +e
out=$(env -i PATH="$deg" "$deg/abd" board 2>&1); rc=$?
set -e
[ "$rc" = "127" ] || fail "expected rc=127 for symlink + degraded PATH, got $rc"
echo "$out" | grep -q 'agent-board:' || fail "expected an agent-board: message, got: $out"
if echo "$out" | grep -q 'readlink'; then fail "leaked a readlink failure to the user: $out"; fi

echo "PASS"
