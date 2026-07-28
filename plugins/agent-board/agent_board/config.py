import copy
import io
import json
import os

CONFIG_NAME = ".agent-board.json"

DEFAULTS = {
    "config_version": 1,
    "project":    {"name": None, "default_branch": None},
    "storage":    {"mode": "git-common-dir", "threads_dir": None, "fsync": True},
    "forge":      {"cli": "auto", "remote": "origin", "cache_ttl_seconds": 300},
    "jobs":       {"scheduler": "auto", "cache_ttl_seconds": 60},
    "thresholds": {"active_commit_days": 3, "parked_idle_days": 7,
                   "needs_attention_idle_hours": 24},
    "collisions": {"enabled": True, "ignore_globs_extra": []},
    "render":     {"engine": "auto"},
    "scan":       {"workers": 8},
}

# env var -> dotted config path
ENV_MAP = {
    "ABD_THREADS_DIR":   "storage.threads_dir",
    "ABD_DEFAULT_BRANCH": "project.default_branch",
    "ABD_FORGE_CLI":     "forge.cli",
    "ABD_SCHEDULER":     "jobs.scheduler",
    "ABD_RENDER_ENGINE": "render.engine",
}


def deep_merge(base, over):
    """Dicts merge recursively; every other type (notably lists) REPLACES."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _set_path(cfg, dotted, value):
    parts = dotted.split(".")
    node = cfg
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value


def _read_json(path, problems):
    try:
        with io.open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (IOError, OSError):
        return None
    except (ValueError, UnicodeDecodeError) as exc:
        problems.append("%s: %s" % (path, exc))
        return None


def load_config(start=None):
    """DEFAULTS < <start>/.agent-board.json < ABD_* env. Never raises."""
    start = start or os.getcwd()
    problems = []
    cfg = copy.deepcopy(DEFAULTS)

    override = os.environ.get("ABD_CONFIG")
    path = override if override else os.path.join(start, CONFIG_NAME)
    found = _read_json(path, problems)
    if isinstance(found, dict):
        cfg = deep_merge(cfg, found)

    for env, dotted in ENV_MAP.items():
        val = os.environ.get(env)
        if val:
            _set_path(cfg, dotted, val)

    cfg["_problems"] = problems
    return cfg
