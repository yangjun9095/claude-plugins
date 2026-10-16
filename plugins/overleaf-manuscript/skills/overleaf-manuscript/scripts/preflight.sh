#!/usr/bin/env bash
# Report how a manuscript folder syncs with Overleaf and whether the local copy is current.
# Usage: bash preflight.sh [REPO_DIR]
# Prints "key: value" lines. The last line starts with "action:".
set -u

dir="${1:-.}"
cd "$dir" 2>/dev/null || { echo "error: cannot enter $dir" >&2; exit 2; }

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "mode: no-git"
  echo "action: cannot pull. Ask the author to confirm that Overleaf has synced and is closed."
  exit 0
fi

echo "repo: $(git rev-parse --show-toplevel)"
echo "branch: $(git branch --show-current)"

url=$(git config --get remote.origin.url || true)
case "$url" in
  *git.overleaf.com*) mode="overleaf-git" ;;
  *github.com*)       mode="github-linked" ;;
  *)                  mode="other" ;;
esac
echo "mode: $mode"
# Show the URL without any user:password@ part. Overleaf tokens are often embedded there.
echo "remote: $(printf '%s\n' "${url:-none}" | sed 's#//[^/@]*@#//#')"

if [ "$mode" = "other" ]; then
  echo "action: unknown sync path. Ask the author how this folder reaches Overleaf."
  exit 0
fi

# Use a timeout when one exists. Stock macOS has neither timeout nor gtimeout.
runner=()
if command -v timeout >/dev/null 2>&1; then
  runner=(timeout 20)
elif command -v gtimeout >/dev/null 2>&1; then
  runner=(gtimeout 20)
fi

# GIT_TERMINAL_PROMPT=0 stops git from waiting for a credential prompt.
if fetch_err=$(GIT_TERMINAL_PROMPT=0 ${runner[@]+"${runner[@]}"} git fetch --quiet origin 2>&1 >/dev/null); then
  fetch_ok=1
  echo "fetch: ok"
else
  fetch_ok=0
  reason=$(printf '%s\n' "$fetch_err" | head -n 1 | sed 's#//[^/@]*@#//#')
  echo "fetch: failed (${reason:-no error text})"
fi

dirty=$(git status --porcelain --untracked-files=no | wc -l | tr -d ' ')
untracked=$(git status --porcelain | grep -c '^??' || true)
echo "dirty: $dirty"
git status --porcelain --untracked-files=no | head -10 | sed 's/^/  /'
echo "untracked: $untracked"

if ! upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null); then
  echo "upstream: none"
  if [ "$fetch_ok" -eq 1 ]; then
    echo "action: no upstream branch. Ask the author which branch Overleaf tracks."
  else
    echo "action: stop and ask. The fetch failed, so the counts may be stale."
  fi
  exit 0
fi
echo "upstream: $upstream"
read -r behind ahead < <(git rev-list --left-right --count '@{u}...HEAD')
echo "behind: $behind"
echo "ahead: $ahead"

if [ "$fetch_ok" -eq 0 ]; then
  echo "action: stop and ask. The fetch failed, so the counts may be stale."
elif [ "$behind" -eq 0 ]; then
  echo "action: up to date. Edit only after approval."
elif [ "$ahead" -eq 0 ] && [ "$dirty" -eq 0 ]; then
  echo "action: run git pull --ff-only"
else
  echo "action: stop and ask. The local copy is not a clean fast-forward of upstream."
fi
