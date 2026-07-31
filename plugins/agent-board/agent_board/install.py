"""`abd install-hooks` -- the fallback when the plugin's own hooks/hooks.json is
not in play (a skills-dir install, or a bare checkout on PATH).

The plugin manifest is the primary path and needs none of this. Hooks merge
across managed / user / project / local / plugin scopes, so installing here is
purely additive.
"""
import io
import json
import os
import subprocess

from agent_board import store

SCOPES = ("user", "project", "local")
EXCLUDE_REL = ".claude/settings.local.json"


def settings_path(scope, repo_root, home=None):
    """Where each scope's settings file lives.

    `local` is the default for a reason: project settings.json is COMMITTED,
    which forces the tool on every collaborator and ships into a public repo,
    and user settings.json fires in every repo on the machine (opt-out, not
    opt-in). Both are offered because a skills-dir install cannot use the
    plugin manifest at all.
    """
    if scope == "user":
        return os.path.join(home or os.path.expanduser("~"), ".claude", "settings.json")
    if scope == "project":
        return os.path.join(repo_root, ".claude", "settings.json")
    if scope == "local":
        return os.path.join(repo_root, ".claude", "settings.local.json")
    raise ValueError("unknown scope %r" % (scope,))


def hook_entries(abd_path):
    """The same two entries as hooks/hooks.json, with ${CLAUDE_PLUGIN_ROOT}
    resolved -- there is no substitution outside the plugin loader. The path is
    quoted because it can contain spaces; commands run through /bin/sh -c.
    2>/dev/null is what makes stderr suppression free, so no wrapper is needed.
    """
    quoted = '"%s"' % abd_path
    return {
        "SessionStart": [{
            "matcher": "startup|resume|fork|clear",
            "hooks": [{
                "type": "command",
                "command": "%s hook session-start 2>/dev/null" % quoted,
                "timeout": 5,
                "statusMessage": "agent-board: loading thread card",
            }],
        }],
        "SessionEnd": [{
            "matcher": "prompt_input_exit|logout|other|bypass_permissions_disabled",
            "hooks": [{
                "type": "command",
                "command": "%s hook session-end 2>/dev/null" % quoted,
                "timeout": 15,
                "async": True,
            }],
        }],
    }


def _is_ours(entry):
    """Match on our exact verb pair, not on the string 'agent-board' -- a user's
    own hook could mention the plugin, and stealing it would be worse than
    duplicating ours."""
    if not isinstance(entry, dict):
        return False
    for hook in entry.get("hooks") or []:
        if not isinstance(hook, dict):
            continue
        command = str(hook.get("command") or "")
        if "hook session-start" in command or "hook session-end" in command:
            return True
    return False


def merge_hooks(settings, entries):
    """Merge ONLY the hooks key. Returns (new_settings, changed).

    Idempotent: a previous agent-board entry is replaced rather than appended, so
    running this twice does not fire the hook twice. Foreign entries in the same
    event array are preserved untouched.
    """
    out = dict(settings)
    raw = out.get("hooks")
    hooks = dict(raw) if isinstance(raw, dict) else {}
    changed = not isinstance(raw, dict) and raw is not None
    for event, ours in entries.items():
        before = hooks.get(event)
        before = list(before) if isinstance(before, list) else []
        after = [e for e in before if not _is_ours(e)] + list(ours)
        if after != before:
            changed = True
        hooks[event] = after
    out["hooks"] = hooks
    return out, changed


def ensure_excluded(common_dir, repo_root):
    """Keep settings.local.json out of git WITHOUT touching .gitignore.

    .gitignore is a TRACKED file: appending to it produces exactly the
    unrequested diff that gets committed into a public repo. info/exclude is
    per-clone and cannot be committed. Do not assume the file is already
    ignored either -- here it is covered by the USER's global ignore file, which
    does not exist in anyone else's clone.
    """
    try:
        proc = subprocess.run(["git", "--no-optional-locks", "-C", repo_root,
                               "check-ignore", "-q", EXCLUDE_REL],
                              capture_output=True, timeout=10)
        if proc.returncode == 0:
            return None                     # already ignored by some rule
    except (subprocess.SubprocessError, OSError):
        pass                                # no git? fall through and write it
    path = os.path.join(common_dir, "info", "exclude")
    line = EXCLUDE_REL + "\n"
    try:
        existing = ""
        if os.path.exists(path):
            with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
                existing = fh.read()
        if EXCLUDE_REL in existing.split():
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write(line)
    except OSError:
        return None
    return path


def install(scope, abd_path, repo_root, common_dir=None, home=None):
    """Returns (rc, [messages]). Prints nothing itself."""
    if scope not in SCOPES:
        return 2, ["abd: unknown scope %r (want: %s)" % (scope, ", ".join(SCOPES))]
    path = settings_path(scope, repo_root, home)

    settings = {}
    if os.path.exists(path):
        text, err = store.read_text_resilient(path)
        if err:
            return 2, ["abd: cannot read %s (%s); left unchanged" % (path, err)]
        if (text or "").strip():
            try:
                parsed = json.loads(text)
            except ValueError as exc:
                # Refuse rather than overwrite. This file is the user's, it may
                # hold settings this tool knows nothing about, and a parse error
                # is not licence to replace it.
                return 2, ["abd: %s is not valid JSON (%s); left unchanged"
                           % (path, exc)]
            if not isinstance(parsed, dict):
                return 2, ["abd: %s does not contain a JSON object; left unchanged"
                           % path]
            settings = parsed

    merged, changed = merge_hooks(settings, hook_entries(abd_path))
    messages = []
    if not changed:
        messages.append("agent-board hooks already installed in %s" % path)
    else:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            store.atomic_write_json(path, merged)
        except OSError as exc:
            return 2, ["abd: cannot write %s (%s)" % (path, exc)]
        messages.append("installed SessionStart + SessionEnd hooks in %s" % path)

    if scope == "local" and common_dir:
        excluded = ensure_excluded(common_dir, repo_root)
        if excluded:
            messages.append("added %s to %s (never .gitignore -- that file is tracked)"
                            % (EXCLUDE_REL, excluded))
    messages.append("restart Claude Code for the hooks to register")
    return 0, messages
