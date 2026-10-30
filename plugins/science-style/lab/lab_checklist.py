"""The checklist of the structure layer (spec section 12): loading, validation, quotes and agreement.

Each item has fields with a type. Closed types (enum, enum_list, objects) hold values from a fixed
list, so a script can count them and compare two extractions. An item with "groups" applies only
to those groups; for any other group its answer is {"not_applicable": true}.
"""
import os

from lab_paths import PLUGIN_ROOT, read_json

CHECKLIST_PATH = os.path.join(PLUGIN_ROOT, "data", "checklist.json")
TOP_KEYS = ("schema", "checklist_version", "prompt_version", "paper_sha256", "work_id", "person", "attempt",
            "run", "answers")
FIELD_TYPES = frozenset(["enum", "enum_list", "objects", "quote", "quotes", "text", "texts", "int", "strings"])
CLOSED_TYPES = frozenset(["enum", "enum_list", "objects"])
NOT_APPLICABLE = {"not_applicable": True}
RUNS = ("main", "agreement")


class ChecklistError(ValueError):
    """The checklist file breaks a rule."""


def load_checklist(path=CHECKLIST_PATH):
    checklist = read_json(path)
    seen = set()
    for item in checklist["items"]:
        if item["id"] in seen:
            raise ChecklistError("item {} appears twice".format(item["id"]))
        seen.add(item["id"])
        for name, spec in item["fields"].items():
            if spec["type"] not in FIELD_TYPES:
                raise ChecklistError("{}.{} has the unknown type {}".format(item["id"], name, spec["type"]))
            if spec["type"] in ("enum", "enum_list") and not spec.get("values"):
                raise ChecklistError("{}.{} needs values".format(item["id"], name))
            if spec["type"] == "objects" and not spec.get("keys"):
                raise ChecklistError("{}.{} needs keys".format(item["id"], name))
    return checklist


def applies(item, group):
    return "groups" not in item or group in item["groups"]


def _str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _field_errors(item_id, name, spec, value):
    where = "{}.{}".format(item_id, name)
    kind = spec["type"]
    if kind == "enum":
        return [] if value in spec["values"] else ["{}: {!r} is not one of {}".format(where, value, spec["values"])]
    if kind == "enum_list":
        if not isinstance(value, list):
            return [where + ": must be a list"]
        return ["{}: {!r} is not one of {}".format(where, v, spec["values"]) for v in value if v not in spec["values"]]
    if kind == "objects":
        if not isinstance(value, list):
            return [where + ": must be a list"]
        errors = []
        expected = set(spec["keys"]) | {"quote"}
        for entry in value:
            if not isinstance(entry, dict):
                errors.append(where + ": each entry must be an object")
                continue
            if set(entry) != expected:
                errors.append("{}: each entry must have the keys {}".format(where, sorted(expected)))
            for key, allowed in spec["keys"].items():
                if key in entry and entry[key] not in allowed:
                    errors.append("{}.{}: {!r} is not one of {}".format(where, key, entry[key], allowed))
            if not isinstance(entry.get("quote"), str) or not entry.get("quote"):
                errors.append(where + ": each entry needs a quote")
        return errors
    if kind == "quote":
        return [] if value is None or isinstance(value, str) else [where + ": must be a string or null"]
    if kind in ("quotes", "texts", "strings"):
        return [] if _str_list(value) else [where + ": must be a list of strings"]
    if kind == "text":
        return [] if isinstance(value, str) else [where + ": must be a string"]
    if kind == "int":
        ok = value is None or (isinstance(value, int) and not isinstance(value, bool))
        return [] if ok else [where + ": must be an integer or null"]
    return [where + ": unknown type"]


def validate_extraction(extraction, checklist, group):
    """Return the list of rule breaks in an extraction. An empty list means it is valid."""
    missing = [key for key in TOP_KEYS if key not in extraction]
    if missing:
        return ["missing keys: " + ", ".join(missing)]
    errors = []
    if extraction["run"] not in RUNS:
        errors.append("run must be main or agreement")
    answers = extraction["answers"]
    if not isinstance(answers, dict):
        return errors + ["answers must be an object"]
    extra = sorted(set(answers) - {i["id"] for i in checklist["items"]})
    if extra:
        errors.append("unknown items: " + ", ".join(extra))
    for item in checklist["items"]:
        answer = answers.get(item["id"])
        if answer is None:
            errors.append(item["id"] + ": missing")
            continue
        if not applies(item, group):
            if answer != NOT_APPLICABLE:
                errors.append(item["id"] + ': must be {"not_applicable": true} for this group')
            continue
        if not isinstance(answer, dict):
            errors.append(item["id"] + ": must be an object")
            continue
        unknown = sorted(set(answer) - set(item["fields"]))
        absent = sorted(set(item["fields"]) - set(answer))
        if unknown:
            errors.append("{}: unknown fields {}".format(item["id"], unknown))
        if absent:
            errors.append("{}: missing fields {}".format(item["id"], absent))
        for name, spec in item["fields"].items():
            if name in answer:
                errors.extend(_field_errors(item["id"], name, spec, answer[name]))
    return errors


def iter_quotes(extraction, checklist):
    """Yield (item_id, field, quote) for every quote in the extraction, in checklist order."""
    answers = extraction.get("answers") or {}
    for item in checklist["items"]:
        answer = answers.get(item["id"])
        if not isinstance(answer, dict) or answer == NOT_APPLICABLE:
            continue
        for name, spec in item["fields"].items():
            value = answer.get(name)
            if spec["type"] == "quote" and isinstance(value, str):
                yield item["id"], name, value
            elif spec["type"] == "quotes" and isinstance(value, list):
                for quote in value:
                    if isinstance(quote, str):
                        yield item["id"], name, quote
            elif spec["type"] == "objects" and isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and isinstance(entry.get("quote"), str):
                        yield item["id"], name, entry["quote"]


def _levenshtein(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def field_agreement(spec, a, b):
    """Return the agreement of two values of a closed field, from 0.0 to 1.0."""
    kind = spec["type"]
    if kind == "enum":
        return 1.0 if a == b else 0.0
    if kind == "enum_list":
        a, b = a or [], b or []
        if not a and not b:
            return 1.0
        return 1.0 - _levenshtein(a, b) / float(max(len(a), len(b)))
    if kind == "objects":
        keys = sorted(spec["keys"])
        set_a = {tuple(e.get(k) for k in keys) for e in (a or []) if isinstance(e, dict)}
        set_b = {tuple(e.get(k) for k in keys) for e in (b or []) if isinstance(e, dict)}
        if not set_a and not set_b:
            return 1.0
        return len(set_a & set_b) / float(len(set_a | set_b))
    raise ValueError("the field type {} has no agreement".format(kind))


def item_agreement(item, answer_a, answer_b):
    """Return the mean agreement of the closed fields of an item, or None when it does not apply."""
    if not isinstance(answer_a, dict) or not isinstance(answer_b, dict):
        return None
    if answer_a == NOT_APPLICABLE or answer_b == NOT_APPLICABLE:
        return None
    scores = [field_agreement(spec, answer_a.get(name), answer_b.get(name))
              for name, spec in item["fields"].items() if spec["type"] in CLOSED_TYPES]
    return sum(scores) / len(scores) if scores else None


def closed_items(checklist):
    return [i for i in checklist["items"] if any(s["type"] in CLOSED_TYPES for s in i["fields"].values())]
