"""Load the merged style of generate-slides-minimal.

load_style() merges these layers in order. A later layer overrides an earlier one.
    1. styles/default.yaml, which holds the lint baseline of the peers profile
    2. styles/themes/<theme>.yaml
    3. styles/profiles/<profile>.yaml, which holds only the numbers that differ
    4. slide-style-minimal.yaml of the project
Dicts merge deeply. Lists and scalars replace. A key with no value is an error.
A value that is not a mapping cannot replace a mapping.
"""
import copy
from pathlib import Path

import yaml

# The data folder is "styles" so that it never shares a name with this module.
STYLES_DIR = Path(__file__).resolve().parent / "styles"

PROFILES = ("peers", "lab-meeting", "general")
THEMES = ("light", "dark")
TOP_LEVEL_KEYS = ("typography", "colors", "layout", "style", "lint")

PROJECT_FILE = "slide-style-minimal.yaml"
# Folders of the project that load_style() searches, in order.
PROJECT_FOLDERS = ("", "docs", ".claude")


def _read_layer(path):
    """Return the mapping in a YAML file. An empty file gives an empty dict."""
    try:
        with open(str(path), encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as error:
        raise ValueError("cannot read the style file {}: {}".format(path, error))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("the style file {} must hold a mapping at the top level".format(path))
    unknown = [key for key in data if key not in TOP_LEVEL_KEYS]
    if unknown:
        raise ValueError(
            "unknown top-level key {} in {}. Valid keys: {}".format(
                ", ".join(repr(key) for key in unknown), path, ", ".join(TOP_LEVEL_KEYS)
            )
        )
    return data


def _merge(base, override, source, path=()):
    """Return a new dict. Dicts merge deeply. Any other value in override replaces.

    Raise ValueError for a key with no value. Raise ValueError for a value that
    is not a mapping where the base holds a mapping. The message names `source`
    and the key path.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        here = ".".join(str(part) for part in path + (key,))
        if value is None:
            raise ValueError(
                "{}: the key {} has no value. Give it a value or remove it.".format(source, here)
            )
        if isinstance(merged.get(key), dict):
            if not isinstance(value, dict):
                raise ValueError(
                    "{}: the key {} must be a mapping. Found {!r}.".format(source, here, value)
                )
            merged[key] = _merge(merged[key], value, source, path + (key,))
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def find_project_file(project_dir):
    """Return the path of the first project style file found, or None.

    The search order is project_dir, then project_dir/docs, then project_dir/.claude.
    A project_dir of None gives None. Raise ValueError for a folder that does not exist.
    """
    if project_dir is None:
        return None
    root = Path(project_dir)
    if not root.is_dir():
        raise ValueError("project directory not found: {}".format(project_dir))
    for folder in PROJECT_FOLDERS:
        candidate = root / folder / PROJECT_FILE
        if candidate.is_file():
            return candidate
    return None


def load_style(profile="peers", theme="light", project_dir=None):
    """Return the merged style as a dict.

    Raise ValueError for an unknown profile or theme and for an unknown top-level
    key in any layer. Raise ValueError for a style file that cannot be read.
    Raise ValueError for a key with no value and for a missing project_dir.
    """
    if profile not in PROFILES:
        raise ValueError(
            "unknown profile {!r}. Valid profiles: {}".format(profile, ", ".join(PROFILES))
        )
    if theme not in THEMES:
        raise ValueError(
            "unknown theme {!r}. Valid themes: {}".format(theme, ", ".join(THEMES))
        )
    paths = [
        STYLES_DIR / "default.yaml",
        STYLES_DIR / "themes" / (theme + ".yaml"),
        STYLES_DIR / "profiles" / (profile + ".yaml"),
    ]
    project_file = find_project_file(project_dir)
    if project_file is not None:
        paths.append(project_file)
    result = {}
    for path in paths:
        result = _merge(result, _read_layer(path), path)
    return result
