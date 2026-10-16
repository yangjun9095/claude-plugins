#!/usr/bin/env bash
# Report how a manuscript folder syncs with Overleaf and whether the local copy is current.
# Usage: bash preflight.sh [REPO_DIR]
# Prints "key: value" lines. The last line starts with "action:".
set -u

dir="${1:-.}"
# CDPATH can make cd print the folder. Send that output away so "repo:" stays the first line.
cd -- "$dir" >/dev/null 2>&1 || { echo "error: cannot enter $dir" >&2; exit 2; }

# Remove a user:password@ part from the URLs in the text on stdin. Overleaf tokens are often
# embedded there. The pattern runs to the last @ before the first slash, so an @ inside a
# password goes too.
redact() { sed 's#//[^/]*@#//#'; }

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "mode: no-git"
  echo "action: cannot pull. Ask the author to confirm that Overleaf has synced and is closed."
  exit 0
fi

echo "repo: $(git rev-parse --show-toplevel)"
if branch=$(git symbolic-ref -q --short HEAD); then
  echo "branch: $branch"
else
  branch=""
  echo "branch: (detached HEAD)"
fi

url=$(git config --get remote.origin.url || true)
case "$url" in
  *git.overleaf.com*) mode="overleaf-git" ;;
  *github.com*)       mode="github-linked" ;;
  *)                  mode="other" ;;
esac
echo "mode: $mode"
echo "remote: $(printf '%s\n' "${url:-none}" | redact)"

if [ "$mode" = "other" ]; then
  echo "action: unknown sync path. Ask the author how this folder reaches Overleaf."
  exit 0
fi

# Fetch the remote that the branch tracks, so the counts below match what git compares against.
# That remote is not always origin. A local upstream (".") or no upstream falls back to origin.
remote_name=""
if [ -n "$branch" ]; then
  remote_name=$(git config --get "branch.$branch.remote" 2>/dev/null || true)
fi
case "$remote_name" in
  ""|.) remote_name="origin" ;;
esac
shown_remote=$(printf '%s\n' "$remote_name" | redact)

# Use a timeout when one exists. Stock macOS has neither timeout nor gtimeout.
runner=()
if command -v timeout >/dev/null 2>&1; then
  runner=(timeout 20)
elif command -v gtimeout >/dev/null 2>&1; then
  runner=(gtimeout 20)
fi

# BatchMode makes ssh fail at once where it would wait for a passphrase or a host-key answer.
# Keep the ssh command that git would use, in git's own order of precedence.
ssh_base="${GIT_SSH_COMMAND:-}"
if [ -z "$ssh_base" ]; then
  ssh_base=$(git config --get core.sshCommand 2>/dev/null || true)
fi
if [ -z "$ssh_base" ]; then
  ssh_base="${GIT_SSH:-ssh}"
fi

# GIT_TERMINAL_PROMPT=0 stops git from waiting for a credential prompt.
if fetch_err=$(GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="$ssh_base -o BatchMode=yes" ${runner[@]+"${runner[@]}"} git fetch --quiet "$remote_name" 2>&1 >/dev/null); then
  fetch_ok=1
  echo "fetch: ok ($shown_remote)"
else
  fetch_ok=0
  reason=$(printf '%s\n' "$fetch_err" | head -n 1 | redact)
  echo "fetch: failed ($shown_remote: ${reason:-no error text})"
fi

dirty=$(git status --porcelain --untracked-files=no | wc -l | tr -d ' ')
untracked=$(git status --porcelain | grep -c '^??' || true)
echo "dirty: $dirty"
git status --porcelain --untracked-files=no | head -10 | sed 's/^/  /'
echo "untracked: $untracked"

if [ -z "$branch" ]; then
  echo "upstream: none"
  echo "action: stop and ask. HEAD is detached; check out a branch first."
  exit 0
fi

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
  unpushed=""
  if [ "$ahead" -eq 1 ]; then
    unpushed=" 1 local commit is not pushed."
  elif [ "$ahead" -gt 1 ]; then
    unpushed=" $ahead local commits are not pushed."
  fi
  echo "action: up to date. Edit only after approval.$unpushed"
elif [ "$ahead" -eq 0 ] && [ "$dirty" -eq 0 ]; then
  echo "action: run git pull --ff-only"
else
  echo "action: stop and ask. The local copy is not a clean fast-forward of upstream."
fi
