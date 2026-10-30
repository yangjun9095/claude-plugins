"""The registry of people, data/people.json (spec section 7).

The orchestrator confirms each identity and writes the entry. The loader checks the shape of each
entry and refuses a repeated id.
"""
import os
import re

from lab_paths import PLUGIN_ROOT, read_json

REGISTRY_PATH = os.path.join(PLUGIN_ROOT, "data", "people.json")
REQUIRED = ("id", "name", "orcid", "openalex_ids", "ml_venues", "confirmed_by")
_ID = re.compile(r"^[a-z][a-z0-9-]*$")
_ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_OPENALEX = re.compile(r"^A\d+$")


class RegistryError(ValueError):
    """The registry breaks a rule. The command line turns it into exit code 2."""


def check_entry(entry):
    """Raise RegistryError when entry breaks a rule."""
    missing = [key for key in REQUIRED if key not in entry]
    if missing:
        raise RegistryError("registry entry {} lacks {}".format(entry.get("id", "?"), ", ".join(missing)))
    if not _ID.match(entry["id"]):
        raise RegistryError("registry id {!r} must use lower case letters, digits and hyphens".format(entry["id"]))
    if not _ORCID.match(entry["orcid"]):
        raise RegistryError("registry entry {} has a malformed ORCID {!r}".format(entry["id"], entry["orcid"]))
    ids = entry["openalex_ids"]
    if not ids or not all(_OPENALEX.match(a) for a in ids):
        raise RegistryError("registry entry {} needs OpenAlex author IDs such as A123".format(entry["id"]))
    if not isinstance(entry["ml_venues"], bool):
        raise RegistryError("registry entry {}: ml_venues must be true or false".format(entry["id"]))


def load_registry(path=REGISTRY_PATH):
    """Return the people in registry order, or raise RegistryError."""
    people = read_json(path).get("people", [])
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
