"""Paths of the style lab: the plugin folder, the data directory and JSON writes.

The data directory holds every full text. The variable STYLE_LAB_DATA names it. The folder must
exist and must be outside the git worktree that holds the plugin, so no full text can enter the
repository.
"""
import json
import os

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_VAR = "STYLE_LAB_DATA"


class PathError(Exception):
    """A path rule failed. The command line turns it into exit code 2."""


def worktree_root(start=PLUGIN_ROOT):
    """Return the nearest folder at or above start that holds a .git entry, or None."""
    folder = os.path.realpath(start)
    while True:
        if os.path.exists(os.path.join(folder, ".git")):
            return folder
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def data_dir(environ=None, worktree=None):
    """Return the real path of the data directory, or raise PathError."""
    environ = os.environ if environ is None else environ
    raw = environ.get(ENV_VAR, "")
    if not raw:
        raise PathError(ENV_VAR + " is not set. Set it to a scratch folder outside the repository.")
    path = os.path.realpath(raw)
    if not os.path.isdir(path):
        raise PathError(ENV_VAR + " names a folder that does not exist: " + path)
    root = worktree_root() if worktree is None else os.path.realpath(worktree)
    if root and (path == root or path.startswith(root + os.sep)):
        raise PathError(ENV_VAR + " points inside the git worktree " + root
                        + ". Full texts must stay outside it.")
    return path


def ensure_dir(*parts):
    """Join the parts, create the folder when it is missing, and return its path."""
    path = os.path.join(*parts)
    os.makedirs(path, exist_ok=True)
    return path


def manifests_dir(data, pilot):
    """Return <data>/pilot/manifests for a pilot run, else the manifests folder of the plugin."""
    return ensure_dir(data, "pilot", "manifests") if pilot else ensure_dir(PLUGIN_ROOT, "manifests")


def profiles_dir(data, pilot):
    """Return <data>/pilot/profiles for a pilot run, else the profiles folder of the plugin."""
    return ensure_dir(data, "pilot", "profiles") if pilot else ensure_dir(PLUGIN_ROOT, "profiles")


def stage_dir(data, pilot, name):
    """Return <data>/pilot/<name> for a pilot run, else <data>/<name>."""
    return ensure_dir(data, "pilot", name) if pilot else ensure_dir(data, name)


def works_path(data, person_id):
    return os.path.join(data, "works", person_id + ".json")


def paper_path(data, person_id, work_id):
    return os.path.join(data, "papers", person_id, work_id + ".json")


def extraction_path(data, person_id, work_id, run="main"):
    """Return the path of an extraction. The main run has no suffix; another run adds its name."""
    suffix = ".json" if run == "main" else "." + run + ".json"
    return os.path.join(data, "extract", person_id, work_id + suffix)


def check_path(data, person_id, work_id, run="main"):
    suffix = ".check.json" if run == "main" else "." + run + ".check.json"
    return os.path.join(data, "extract", person_id, work_id + suffix)


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, obj):
    """Write obj as UTF-8 JSON through a temporary file, so a crash leaves the old file whole."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def write_json_guarded(path, obj, force=False):
    """Write obj unless the existing file holds more papers.

    The old and the new object carry the count in "n_papers". With force=True the write always
    happens.
    """
    if not force and os.path.exists(path):
        old = read_json(path).get("n_papers", 0)
        new = obj.get("n_papers", 0)
        if new < old:
            raise PathError("refusing to replace {}: it holds {} papers and the new file holds {}. "
                            "Use --force to replace it.".format(path, old, new))
    write_json(path, obj)
