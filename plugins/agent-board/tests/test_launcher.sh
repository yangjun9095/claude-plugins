#!/bin/sh
# Launcher contract tests. Run under BOTH dash and bash.
set -eu
ABD_BIN="$(dirname "$0")/../bin/abd"
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

echo "PASS"
