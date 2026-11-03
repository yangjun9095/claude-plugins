"""Venue tiers and essay venues (spec sections 7 and 8).

A name matches without regard to case or repeated spaces. A prefix matches when the venue name
starts with it and the next character is not a letter or digit, so "Nature" matches
"Nature Genetics" and "Nature Reviews. Genetics" but not "Naturwissenschaften".
"""
import os

from lab_paths import PLUGIN_ROOT, read_json

VENUES_PATH = os.path.join(PLUGIN_ROOT, "data", "venues.json")


def load_venues(path=VENUES_PATH):
    return read_json(path)


def _key(name):
    return " ".join((name or "").split()).casefold()


def _has_prefix(name, prefix):
    key = _key(prefix)
    return name.startswith(key) and (len(name) == len(key) or not name[len(key)].isalnum())


def tier_of(venue, venues, ml_venues=False):
    """Return "high" or "other" for an OpenAlex venue name. A missing name is "other"."""
    name = _key(venue)
    if not name:
        return "other"
    if name in {_key(v) for v in venues["high_exact"]}:
        return "high"
    if ml_venues and name in {_key(v) for v in venues["ml_high"]}:
        return "high"
    if name in {_key(v) for v in venues["high_prefix_exclude"]}:
        return "other"
    if any(_has_prefix(name, p) for p in venues["high_prefix"]):
        return "high"
    return "other"


def is_essay_venue(venue, venues):
    """Return True when the venue name starts with an essay prefix such as "Trends in"."""
    name = _key(venue)
    return bool(name) and any(_has_prefix(name, p) for p in venues["essay_prefix"])
