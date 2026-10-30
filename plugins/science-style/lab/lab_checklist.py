"""The checklist of the structure layer (spec section 12): loading, validation, quotes and agreement.

Each item has fields with a type. Closed types (enum, enum_list, objects) hold values from a fixed
list, so a script can count them and compare two extractions. An item with "groups" applies only
to those groups; for any other group its answer is {"not_applicable": true}. An item with
"may_be_not_applicable": true accepts the same answer in any group, for a paper that has no text
for the item (for example, no section of kind results).

An item may have an "evidence" key. It names a controlling field, and for each value of that field
it lists what the other fields must hold. The "filled" fields need a non-empty quote, list or
integer of 1 or more. The "empty" fields need null or an empty list. The "is" fields need one given
value. The "is_not" fields need any other value. The case "*" covers every value without a case.
"""
import os

from lab_paths import PLUGIN_ROOT, read_json

CHECKLIST_PATH = os.path.join(PLUGIN_ROOT, "data", "checklist.json")
PROMPT_VERSION = 2
TOP_KEYS = ("schema", "checklist_version", "prompt_version", "paper_sha256", "work_id", "person", "attempt",
            "run", "answers")
FIELD_TYPES = frozenset(["enum", "enum_list", "objects", "quote", "quotes", "text", "texts", "int", "strings"])
CLOSED_TYPES = frozenset(["enum", "enum_list", "objects"])
NOT_APPLICABLE = {"not_applicable": True}
RUNS = ("main", "agreement")
ANY_VALUE = "*"
EVIDENCE_RULES = ("filled", "empty", "is", "is_not")


class ChecklistError(ValueError):
    """The checklist file breaks a rule."""


def load_checklist(path=CHECKLIST_PATH):
    checklist = read_json(path)
    seen = set()
    for item in checklist["items"]:
        if item["id"] in seen:
            raise ChecklistError("item {} appears twice".format(item["id"]))
        seen.add(item["id"])
        if "may_be_not_applicable" in item:
            if not isinstance(item["may_be_not_applicable"], bool):
                raise ChecklistError("{}: may_be_not_applicable must be true or false".format(item["id"]))
        for name, spec in item["fields"].items():
            if spec["type"] not in FIELD_TYPES:
                raise ChecklistError("{}.{} has the unknown type {}".format(item["id"], name, spec["type"]))
            if spec["type"] in ("enum", "enum_list") and not spec.get("values"):
                raise ChecklistError("{}.{} needs values".format(item["id"], name))
            if spec["type"] == "objects" and not spec.get("keys"):
                raise ChecklistError("{}.{} needs keys".format(item["id"], name))
        _check_evidence(item)
    return checklist


def _check_evidence(item):
    """Raise ChecklistError when the evidence rules of an item name an unknown field, value or rule."""
    evidence = item.get("evidence", {})
    fields = item["fields"]
    if not isinstance(evidence, dict):
        raise ChecklistError("{}: evidence must be an object".format(item["id"]))

    def known(name, where):
        if name not in fields:
            raise ChecklistError("{}: evidence names the unknown field {} in {}".format(item["id"], name, where))

    def listed(rule, key, where):
        names = rule.get(key, [])
        if not isinstance(names, list):
            raise ChecklistError("{}: evidence {} in {} must be a list".format(item["id"], key, where))
        for name in names:
            known(name, where)

    for control, cases in evidence.items():
        known(control, "the controlling field")
        if fields[control]["type"] != "enum" or not isinstance(cases, dict):
            raise ChecklistError("{}: evidence for {} needs an enum field and an object".format(item["id"], control))
        for value, rule in cases.items():
            where = "{}={}".format(control, value)
            if value != ANY_VALUE and value not in fields[control]["values"]:
                raise ChecklistError("{}: evidence names the unknown value {} of {}".format(item["id"], value, control))
            if not isinstance(rule, dict) or set(rule) - set(EVIDENCE_RULES):
                raise ChecklistError("{}: evidence in {} must use only {}".format(item["id"], where, EVIDENCE_RULES))
            listed(rule, "filled", where)
            listed(rule, "empty", where)
            for key in ("is", "is_not"):
                for name, wanted in rule.get(key, {}).items():
                    known(name, where)
                    if fields[name]["type"] == "enum" and wanted not in fields[name]["values"]:
                        raise ChecklistError("{}: evidence names the unknown value {} of {}".format(
                            item["id"], wanted, name))


def applies(item, group):
    return "groups" not in item or group in item["groups"]


def may_be_not_applicable(item):
    """Return True when the item accepts {"not_applicable": true} in any group."""
    return item.get("may_be_not_applicable") is True


def _str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_filled(value):
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, list):
        return len(value) > 0
    return _is_int(value) and value >= 1


def _is_empty(value):
    return value is None or value == []


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
        return [] if value is None or _is_int(value) else [where + ": must be an integer or null"]
    return [where + ": unknown type"]


def _evidence_errors(item, answer):
    """Return the errors of the evidence rules of an item for one answer."""
    errors = []
    for control, cases in item.get("evidence", {}).items():
        value = answer[control]
        if value not in item["fields"][control]["values"]:
            continue
        rule = cases.get(value, cases.get(ANY_VALUE, {}))
        when = "when {} is {!r}".format(control, value)
        for name in rule.get("filled", []):
            if not _is_filled(answer[name]):
                errors.append("{}.{}: must be filled {}".format(item["id"], name, when))
        for name in rule.get("empty", []):
            if not _is_empty(answer[name]):
                errors.append("{}.{}: must be null or empty {}".format(item["id"], name, when))
        for name, wanted in rule.get("is", {}).items():
            if answer[name] != wanted:
                errors.append("{}.{}: must be {!r} {}".format(item["id"], name, wanted, when))
        for name, wanted in rule.get("is_not", {}).items():
            if answer[name] == wanted:
                errors.append("{}.{}: must not be {!r} {}".format(item["id"], name, wanted, when))
    return errors


def validate_extraction(extraction, checklist, group):
    """Return the list of rule breaks in an extraction. An empty list means it is valid."""
    if not isinstance(extraction, dict):
        return ["extraction is not an object"]
    missing = [key for key in TOP_KEYS if key not in extraction]
    if missing:
        return ["missing keys: " + ", ".join(missing)]
    errors = []
    for key in ("schema", "checklist_version", "prompt_version", "attempt"):
        if not _is_int(extraction[key]):
            errors.append(key + ": must be an integer")
    if _is_int(extraction["attempt"]) and extraction["attempt"] < 1:
        errors.append("attempt: must be 1 or more")
    for key in ("paper_sha256", "work_id", "person", "run"):
        if not isinstance(extraction[key], str):
            errors.append(key + ": must be a string")
    if isinstance(extraction["run"], str) and extraction["run"] not in RUNS:
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
        if answer == NOT_APPLICABLE and may_be_not_applicable(item):
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
        if not absent:
            errors.extend(_evidence_errors(item, answer))
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
