"""The registry of people and teams, data/people.json (spec section 7).

The orchestrator confirms each identity and writes the entry. The loader checks the shape of each
entry and refuses a repeated id. A team entry has a list of members, the ids of individual entries,
and no ORCID or OpenAlex ID. A team stands for the joint papers of its members.
"""
import os
import re

from lab_paths import PLUGIN_ROOT, read_json

REGISTRY_PATH = os.path.join(PLUGIN_ROOT, "data", "people.json")
REQUIRED = ("id", "name", "orcid", "openalex_ids", "ml_venues", "confirmed_by")
TEAM_REQUIRED = ("id", "name", "members", "confirmed_by")
TEAM_FORBIDDEN = ("orcid", "openalex_ids")
MIN_MEMBERS = 2
_ID = re.compile(r"[a-z][a-z0-9-]*", re.ASCII)
_ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", re.ASCII)
_OPENALEX = re.compile(r"A\d+", re.ASCII)


class RegistryError(ValueError):
    """The registry breaks a rule. The command line turns it into exit code 2."""


def is_team(entry):
    """Return True for a team entry: a dict with a members list."""
    return isinstance(entry, dict) and "members" in entry


def _check_id(entry):
    if not isinstance(entry["id"], str):
        raise RegistryError("registry entry {}: id must be a string".format(entry["id"]))
    if not _ID.fullmatch(entry["id"]):
        raise RegistryError("registry id {!r} must use lower case letters, digits and hyphens".format(entry["id"]))


def _check_team(entry):
    missing = [key for key in TEAM_REQUIRED if key not in entry]
    if missing:
        raise RegistryError("registry team {} lacks {}".format(entry.get("id", "?"), ", ".join(missing)))
    _check_id(entry)
    present = [key for key in TEAM_FORBIDDEN if key in entry]
    if present:
        raise RegistryError("registry team {} must not have {}".format(entry["id"], ", ".join(present)))
    members = entry["members"]
    if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
        raise RegistryError("registry team {}: members must be a list of strings".format(entry["id"]))
    if len(members) < MIN_MEMBERS:
        raise RegistryError("registry team {} needs at least {} members".format(entry["id"], MIN_MEMBERS))
    repeated = sorted({m for m in members if members.count(m) > 1})
    if repeated:
        raise RegistryError("registry team {} lists {} twice".format(entry["id"], ", ".join(repeated)))


def check_team_members(entry, by_id):
    """Raise RegistryError when a member of the team is not an individual entry of by_id."""
    for member in entry["members"]:
        found = by_id.get(member)
        if found is None:
            raise RegistryError("registry team {}: unknown member {}".format(entry["id"], member))
        if is_team(found):
            raise RegistryError("registry team {}: member {} is a team".format(entry["id"], member))


def check_entry(entry, by_id=None):
    """Raise RegistryError when entry breaks a rule.

    Each pattern must match the whole value, in ASCII, so a trailing line break or a non-ASCII digit
    fails. The id becomes part of file names. A team entry has the keys of TEAM_REQUIRED. When by_id
    maps each id of the registry to its entry, the function also checks the members of a team.
    """
    if not isinstance(entry, dict):
        raise RegistryError("registry entry {!r} must be a JSON object".format(entry))
    if is_team(entry):
        _check_team(entry)
        if by_id is not None:
            check_team_members(entry, by_id)
        return
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
    """Return the people and teams in registry order, or raise RegistryError."""
    try:
        data = read_json(path)
    except (OSError, ValueError) as error:
        raise RegistryError("cannot read the registry {}: {}".format(path, error)) from error
    if not isinstance(data, dict):
        raise RegistryError("the registry {} must hold a JSON object".format(path))
    people = data.get("people", [])
    if not isinstance(people, list):
        raise RegistryError("the registry {}: people must be a list".format(path))
    by_id = {}
    for entry in people:
        check_entry(entry)
        if entry["id"] in by_id:
            raise RegistryError("registry id {} appears twice".format(entry["id"]))
        by_id[entry["id"]] = entry
    for entry in people:
        if is_team(entry):
            check_team_members(entry, by_id)
    return people


def get_person(people, person_id):
    for person in people:
        if person["id"] == person_id:
            return person
    raise RegistryError("no person with the id {!r} in the registry".format(person_id))


def team_members(people, team):
    """Return the entries of the members of a team, in the order of the team's members list."""
    return [get_person(people, member) for member in team["members"]]
