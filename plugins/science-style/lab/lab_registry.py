"""The registry of people, data/people.json (spec section 7).

The orchestrator confirms each identity and writes the entry. The loader checks the shape of each
entry and refuses a repeated id.
"""
import os
import re

from lab_paths import PLUGIN_ROOT, read_json

REGISTRY_PATH = os.path.join(PLUGIN_ROOT, "data", "people.json")
REQUIRED = ("id", "name", "orcid", "openalex_ids", "ml_venues", "confirmed_by")
_ID = re.compile(r"[a-z][a-z0-9-]*", re.ASCII)
_ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", re.ASCII)
_OPENALEX = re.compile(r"A\d+", re.ASCII)


class RegistryError(ValueError):
    """The registry breaks a rule. The command line turns it into exit code 2."""


def check_entry(entry):
    """Raise RegistryError when entry breaks a rule.

    Each pattern must match the whole value, in ASCII, so a trailing line break or a non-ASCII digit
    fails. The id becomes part of file names.
    """
    if not isinstance(entry, dict):
        raise RegistryError("registry entry {!r} must be a JSON object".format(entry))
    missing = [key for key in REQUIRED if key not in entry]
    if missing:
        raise RegistryError("registry entry {} lacks {}".format(entry.get("id", "?"), ", ".join(missing)))
    for key in ("id", "orcid"):
        if not isinstance(entry[key], str):
            raise RegistryError("registry entry {}: {} must be a string".format(entry["id"], key))
    ids = entry["openalex_ids"]
    if not isinstance(ids, list) or not all(isinstance(a, str) for a in ids):
        raise RegistryError("registry entry {}: openalex_ids must be a list of strings".format(entry["id"]))
    if not _ID.fullmatch(entry["id"]):
        raise RegistryError("registry id {!r} must use lower case letters, digits and hyphens".format(entry["id"]))
    if not _ORCID.fullmatch(entry["orcid"]):
        raise RegistryError("registry entry {} has a malformed ORCID {!r}".format(entry["id"], entry["orcid"]))
    if not ids or not all(_OPENALEX.fullmatch(a) for a in ids):
        raise RegistryError("registry entry {} needs OpenAlex author IDs such as A123".format(entry["id"]))
    if not isinstance(entry["ml_venues"], bool):
        raise RegistryError("registry entry {}: ml_venues must be true or false".format(entry["id"]))


def load_registry(path=REGISTRY_PATH):
    """Return the people in registry order, or raise RegistryError."""
    try:
        data = read_json(path)
    except (OSError, ValueError) as error:
        raise RegistryError("cannot read the registry {}: {}".format(path, error)) from error
    if not isinstance(data, dict):
        raise RegistryError("the registry {} must hold a JSON object".format(path))
    people = data.get("people", [])
    if not isinstance(people, list):
        raise RegistryError("the registry {}: people must be a list".format(path))
    seen = set()
    for entry in people:
        check_entry(entry)
        if entry["id"] in seen:
            raise RegistryError("registry id {} appears twice".format(entry["id"]))
        seen.add(entry["id"])
    return people


def get_person(people, person_id):
    for person in people:
        if person["id"] == person_id:
            return person
    raise RegistryError("no person with the id {!r} in the registry".format(person_id))
