"""Load and check the pattern data of plain-prose and the project file prose-style.yaml.

`load_patterns(project_dir=None, data_path=None)` reads data/patterns.json and checks it. It
merges the project file when `project_dir` holds one. It returns a `Patterns` object. A bad
data file or a bad project file raises `PatternError`. The message is a plain sentence. It
names the family id and the rule label, or the key of the project file.

The data file is `{"version": 1, "as_of": "<date>", "families": [...]}`.

A family has these fields.
- `id`, `title`, `mode`, `strategy`, `delete_ok`, and an optional `note`.
- `mode` is `each` (flag every hit) or `density` (flag the hits only above `max_per_1000`).
- A density family needs `max_per_1000` above zero. An `each` family has `null` there.
- A family with regex rules has `rules`.
- A structural family has `check`, `params`, `tier` and `sources` instead of rules.

A structural family runs one of three checks. Task 5 reads the params.
- `repeated_openers`: `run`, `ignore` and `ignored_compare_words`.
- `staccato`: `run` and `max_words`.
- `question_answer`: `answers` and `skip_paragraph_start`.

A rule has these fields.
- `tier` (T1, T2 or T3), `sources` (keys such as `corpus:S1`) and `label`.
- A `label` is a short name that findings show.
- Exactly one of `regex` and `words`.
- Optional: `unless`, a regex. The rule stays quiet when it matches the sentence.
- Optional: `unless_citation`. The rule stays quiet when the sentence holds a citation span.
- Optional: `case_sensitive`, true for sentence-start patterns.
- Optional: `lower_only`, true for a `words` rule. The first letter of the word must be lower
  case in the text, so a surname such as Foster stays quiet.
- A sentence that starts with a `lower_only` word is missed.
- Optional: `severity`, `flag` (the default) or `info`.
- The detector reports a hit of an `info` rule with severity `info`, also in an `each` family.
- Optional: `note`, a science exception or a caveat.

`Rule.fires(sentence, cited=False)` applies a rule to one masked sentence. It returns True when
the regex matches and `unless` does not. With `unless_citation` and `cited` true it returns False.
The detector passes `cited` true when the sentence holds a placeholder of a citation span.

A source key is `<note>:S<n>`. The notes are corpus, wikipedia, guides, authors and craft.
The key resolves to a line `- S<n> ` in the "Pages opened" or "Files read" section of the note.

Every regex is written for Python `re`. It is compiled with `re.I` unless the rule says
`"case_sensitive": true`. `unless` follows the same flag. The detector runs a rule on one
masked sentence. `^` matches the start of that sentence. A regex must not depend on text
inside a placeholder (U+E000, digits, U+E001).

Word notation. A `words` rule compiles to one regex with a leading word boundary. Each entry
is a word stem or an exact word.
- `delv*` is a stem. It matches delve, delves, delved and delving.
- `delve` is an exact word. It matches `delve` and no other form.
- A hyphen or a space inside an entry matches hyphens or whitespace.
- So `cutting-edge` matches `cutting edge`, and `deep dive` matches `deep-dive`.
- An entry holds letters, single hyphens or spaces, and at most one `*` at the end.

Project file. `prose-style.yaml` has two optional keys.
- `families: {<id>: {...}}` changes a family. The keys are `enabled`, `max_per_1000`, `mode` and
  `disable_labels`.
- `enabled: false` switches a family off.
- `max_per_1000: N` changes the threshold. It needs density mode.
- `mode: each|density` changes the mode. A structural family keeps its mode.
- `disable_labels: [label, ...]` turns off the rules with those labels.
- `extra_patterns: [{id, title, regex or words, strategy, mode, max_per_1000, unless}]` adds a
  family of one rule.
- The rule of an extra pattern gets tier T3 and the source key `project:<file name>`.

An unknown family id, an unknown key, an unknown label, a bad type or a bad regex raises
`PatternError`. So does an override that changes nothing. `Patterns.disabled` keeps the
families that the project file switched off. `Family.disabled_rules` keeps the rules that
`disable_labels` turned off.
"""
import copy
import json
import os
import re
from collections import OrderedDict

import yaml

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(os.path.dirname(SCRIPTS_DIR), "data", "patterns.json")
PROJECT_FILE_NAME = "prose-style.yaml"
PROJECT_FOLDERS = ("", "docs", ".claude")

TIERS = ("T1", "T2", "T3")
SEVERITIES = ("flag", "info")
MODES = ("each", "density")
NOTE_NAMES = ("corpus", "wikipedia", "guides", "authors", "craft")
CHECKS = {
    "repeated_openers": {"run": "count", "ignore": "words", "ignored_compare_words": "count"},
    "staccato": {"run": "count", "max_words": "count"},
    "question_answer": {"answers": "words", "skip_paragraph_start": "bool"},
}

_SOURCE_KEY = re.compile(r"^(?:%s):S[1-9][0-9]*$" % "|".join(NOTE_NAMES))
_ID = re.compile(r"^[a-z][a-z0-9-]*$")
_ENTRY = re.compile(r"^[A-Za-z]+(?:[- ][A-Za-z]+)*\*?$")
_DATA_KEYS = ("version", "as_of", "families")
_FAMILY_KEYS = ("id", "title", "mode", "max_per_1000", "strategy", "delete_ok", "note",
                "rules", "check", "params", "tier", "sources")
_RULE_KEYS = ("tier", "sources", "label", "regex", "words", "unless", "unless_citation",
              "case_sensitive", "lower_only", "severity", "note")
_OVERRIDE_KEYS = ("enabled", "max_per_1000", "mode", "disable_labels")
_EXTRA_KEYS = ("id", "title", "regex", "words", "strategy", "mode", "max_per_1000", "unless")
_PROJECT_KEYS = ("families", "extra_patterns")


class PatternError(ValueError):
    """The pattern data or the project file is wrong. The message says what and where."""


class Rule(object):
    """One regex rule. `regex` is compiled. `unless` is compiled or None."""

    def __init__(self, tier, sources, label, regex, words=None, unless=None,
                 unless_citation=False, case_sensitive=False, lower_only=False, severity="flag", note=None):
        self.tier = tier
        self.sources = list(sources)
        self.label = label
        self.regex = regex
        self.words = list(words) if words is not None else None
        self.unless = unless
        self.unless_citation = unless_citation
        self.case_sensitive = case_sensitive
        self.lower_only = lower_only
        self.severity = severity
        self.note = note

    def fires(self, sentence, cited=False):
        """Return True when the rule flags the masked sentence. See the module docstring."""
        if self.unless_citation and cited:
            return False
        if not self.regex.search(sentence):
            return False
        return self.unless is None or not self.unless.search(sentence)

    def __repr__(self):
        return "Rule(%r, %s)" % (self.label, self.tier)


class Family(object):
    """One family. A structural family has `check` and `params`, and no rules.

    A regex family keeps its tier on each rule, so `tier` and `sources` are None. A structural
    family keeps them on the family.
    """

    def __init__(self, id, title, mode, max_per_1000, strategy, delete_ok, rules=None,
                 check=None, params=None, tier=None, sources=None, note=None, enabled=True,
                 disabled_rules=None):
        self.id = id
        self.title = title
        self.mode = mode
        self.max_per_1000 = max_per_1000
        self.strategy = strategy
        self.delete_ok = delete_ok
        self.rules = list(rules) if rules else []
        self.check = check
        self.params = dict(params) if params else {}
        self.tier = tier
        self.sources = list(sources) if sources else None
        self.note = note
        self.enabled = enabled
        self.disabled_rules = list(disabled_rules) if disabled_rules else []

    def __repr__(self):
        return "Family(%r, %s)" % (self.id, self.mode)


class Patterns(object):
    """The families in the order of the data file, then the extra patterns."""

    def __init__(self, families, as_of, disabled=None):
        self.families = list(families)
        self.as_of = as_of
        self.disabled = list(disabled) if disabled else []

    def family(self, family_id):
        """Return the family with this id, enabled or not. Raise KeyError when none has it."""
        for family in self.families + self.disabled:
            if family.id == family_id:
                return family
        raise KeyError("no family with the id %r" % (family_id,))


def words_pattern(entries, case_sensitive=False, lower_only=False):
    """Compile a word list to one regex. See the module docstring for the notation.

    With `lower_only` the first letter of each entry must be a lower-case letter in the text, so a
    surname such as Foster does not match `foster*`. The rest of the word stays case-insensitive.
    """
    if not isinstance(entries, (list, tuple)) or not entries:
        raise PatternError("A word list needs at least one entry.")
    parts = []
    for entry in entries:
        if not isinstance(entry, str) or not _ENTRY.match(entry):
            raise PatternError(
                "The word entry %r is not valid. Use letters, single hyphens or spaces, "
                "and one * at the end." % (entry,))
        stem = entry.endswith("*")
        body = entry[:-1] if stem else entry
        if lower_only and not entry[0].islower():
            raise PatternError("The word entry %r must start with a lower-case letter when 'lower_only' is set." % (entry,))
        piece = "".join(r"[-\s]+" if char in "- " else re.escape(char) for char in body)
        if lower_only and not case_sensitive:
            piece = "(?-i:%s)%s" % (re.escape(body[0]), piece[len(re.escape(body[0])):])
        parts.append(piece + (r"\w*" if stem else ""))
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", 0 if case_sensitive else re.I)


def find_project_file(project_dir):
    """Return the first existing prose-style.yaml in ./, docs/ and .claude/, or None."""
    if project_dir is None:
        return None
    for folder in PROJECT_FOLDERS:
        path = os.path.join(project_dir, folder, PROJECT_FILE_NAME) if folder else \
            os.path.join(project_dir, PROJECT_FILE_NAME)
        if os.path.isfile(path):
            return path
    return None


def load_patterns(project_dir=None, data_path=None):
    """Read and check the data file, then merge the project file of `project_dir` if any."""
    path = data_path or DATA_FILE
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle, object_pairs_hook=OrderedDict)
    except OSError as error:
        raise PatternError("The pattern data file '%s' cannot be read: %s." % (name, error.strerror or error))
    except ValueError as error:
        raise PatternError("The pattern data file '%s' is not valid JSON: %s." % (name, error))
    try:
        patterns = parse_data(data)
    except PatternError as error:
        raise PatternError("Pattern data file '%s': %s" % (name, error))
    project_path = find_project_file(project_dir)
    if project_path is None:
        return patterns
    project_name = os.path.basename(project_path)
    try:
        with open(project_path, encoding="utf-8") as handle:
            project = yaml.safe_load(handle)
    except OSError as error:
        raise PatternError("The project file '%s' cannot be read: %s." % (project_name, error.strerror or error))
    except yaml.YAMLError as error:
        raise PatternError("The project file '%s' is not valid YAML: %s." % (
            project_name, str(error).replace("\n", " ")))
    return apply_project(patterns, project, project_name)


# ---------------------------------------------------------------------------------------
# The data file
# ---------------------------------------------------------------------------------------

def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _fail(where, text):
    raise PatternError("%s: %s" % (where, text))


def _check_keys(mapping, allowed, where, kind):
    for key in mapping:
        if key not in allowed:
            _fail(where, "the %s key '%s' is unknown. The valid keys are %s." % (kind, key, ", ".join(allowed)))


def _text(mapping, key, where):
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail(where, "'%s' must be a non-empty text." % key)
    return value


def _sources(mapping, where):
    sources = mapping.get("sources")
    if not isinstance(sources, list) or not sources:
        _fail(where, "'sources' must be a non-empty list of source keys.")
    for key in sources:
        if isinstance(key, str) and re.match(r"^[a-z]+:S[1-9][0-9]*$", key) and key.split(":")[0] not in NOTE_NAMES:
            _fail(where, "the source key %r names an unknown note. The known notes are %s." % (key, ", ".join(NOTE_NAMES)))
        if not isinstance(key, str) or not _SOURCE_KEY.match(key):
            _fail(where, "the source key %r does not have the form <note>:S<n>. The known notes are %s." % (
                key, ", ".join(NOTE_NAMES)))
    if len(set(sources)) != len(sources):
        _fail(where, "'sources' holds a key twice.")
    return sources


def _tier(mapping, where):
    tier = mapping.get("tier")
    if tier not in TIERS:
        _fail(where, "'tier' must be T1, T2 or T3, not %r." % (tier,))
    return tier


def _compile(pattern, case_sensitive, where, name):
    flags = 0 if case_sensitive else re.I
    try:
        compiled = re.compile(pattern, flags)
    except (re.error, OverflowError, RecursionError) as error:
        _fail(where, "the %s does not compile: %s." % (name, error))
    if compiled.search(""):
        _fail(where, "the %s matches an empty string." % name)
    return compiled


def _parse_pattern(mapping, case_sensitive, where, lower_only=False):
    """Return (regex, words, unless) of a rule or an extra pattern."""
    has_regex, has_words = "regex" in mapping, "words" in mapping
    if has_regex == has_words:
        _fail(where, "a rule needs exactly one of 'regex' and 'words'.")
    words = None
    if has_regex:
        pattern = mapping["regex"]
        if not isinstance(pattern, str) or not pattern:
            _fail(where, "'regex' must be a non-empty text.")
        regex = _compile(pattern, case_sensitive, where, "regex")
    else:
        words = mapping["words"]
        try:
            pattern = words_pattern(words, case_sensitive, lower_only)
        except PatternError as error:
            _fail(where, str(error))
        regex = _compile(pattern.pattern, case_sensitive, where, "regex")
    unless = None
    if mapping.get("unless") is not None:
        text = mapping["unless"]
        if not isinstance(text, str) or not text:
            _fail(where, "'unless' must be a non-empty text.")
        unless = _compile(text, case_sensitive, where, "unless regex")
    return regex, (list(words) if words is not None else None), unless


def _parse_rule(mapping, family_id, number):
    where = "Family '%s', rule number %d" % (family_id, number)
    if not isinstance(mapping, dict):
        _fail("Family '%s'" % family_id, "rule number %d must be a mapping." % number)
    label = mapping.get("label")
    if isinstance(label, str) and label.strip():
        where = "Family '%s', rule '%s'" % (family_id, label)
    _check_keys(mapping, _RULE_KEYS, where, "rule")
    _text(mapping, "label", where)
    tier = _tier(mapping, where)
    sources = _sources(mapping, where)
    unless_citation = mapping.get("unless_citation", False)
    if not isinstance(unless_citation, bool):
        _fail(where, "'unless_citation' must be true or false.")
    case_sensitive = mapping.get("case_sensitive", False)
    if not isinstance(case_sensitive, bool):
        _fail(where, "'case_sensitive' must be true or false.")
    note = mapping.get("note")
    if note is not None and (not isinstance(note, str) or not note.strip()):
        _fail(where, "'note' must be a non-empty text.")
    lower_only = mapping.get("lower_only", False)
    if not isinstance(lower_only, bool):
        _fail(where, "'lower_only' must be true or false.")
    if lower_only and "words" not in mapping:
        _fail(where, "'lower_only' needs a 'words' list.")
    severity = mapping.get("severity", "flag")
    if severity not in SEVERITIES:
        _fail(where, "'severity' must be flag or info, not %r." % (severity,))
    regex, words, unless = _parse_pattern(mapping, case_sensitive, where, lower_only)
    return Rule(tier, sources, label, regex, words, unless, unless_citation, case_sensitive, lower_only, severity, note)


def _check_params(check, params, where):
    if check not in CHECKS:
        _fail(where, "the check %r is unknown. Use one of %s." % (check, ", ".join(sorted(CHECKS))))
    if not isinstance(params, dict):
        _fail(where, "'params' must be a mapping.")
    spec = CHECKS[check]
    for key in params:
        if key not in spec:
            _fail(where, "the parameter '%s' is unknown for the check %s." % (key, check))
    for key, kind in spec.items():
        if key not in params:
            _fail(where, "the parameter '%s' is missing." % key)
        value = params[key]
        if kind == "count":
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                _fail(where, "the parameter '%s' must be a whole number of 1 or more." % key)
        elif kind == "bool":
            if not isinstance(value, bool):
                _fail(where, "the parameter '%s' must be true or false." % key)
        elif not isinstance(value, list) or not all(isinstance(w, str) and w for w in value):
            _fail(where, "the parameter '%s' must be a list of words." % key)
        elif key == "answers" and not value:
            _fail(where, "the parameter 'answers' must not be empty.")


def _parse_family(mapping, number):
    if not isinstance(mapping, dict):
        raise PatternError("Family number %d must be a mapping." % number)
    family_id = mapping.get("id")
    if not isinstance(family_id, str) or not _ID.match(family_id):
        raise PatternError("Family number %d has no valid id." % number)
    where = "Family '%s'" % family_id
    _check_keys(mapping, _FAMILY_KEYS, where, "family")
    title = _text(mapping, "title", where)
    strategy = _text(mapping, "strategy", where)
    mode = mapping.get("mode")
    if mode not in MODES:
        _fail(where, "'mode' must be each or density, not %r." % (mode,))
    max_per_1000 = mapping.get("max_per_1000")
    if mode == "density":
        if not _is_number(max_per_1000) or max_per_1000 <= 0:
            _fail(where, "a density family needs 'max_per_1000' above zero.")
    elif max_per_1000 is not None:
        _fail(where, "an each family must have 'max_per_1000' set to null.")
    delete_ok = mapping.get("delete_ok")
    if not isinstance(delete_ok, bool):
        _fail(where, "'delete_ok' must be true or false.")
    note = mapping.get("note")
    if note is not None and (not isinstance(note, str) or not note.strip()):
        _fail(where, "'note' must be a non-empty text.")
    has_rules, has_check = "rules" in mapping, "check" in mapping
    if has_rules == has_check:
        _fail(where, "a family needs exactly one of 'rules' and 'check'.")
    if has_rules:
        for key in ("params", "tier", "sources"):
            if key in mapping:
                _fail(where, "a family with rules keeps '%s' on its rules." % key)
        rules_data = mapping["rules"]
        if not isinstance(rules_data, list) or not rules_data:
            _fail(where, "'rules' must be a non-empty list.")
        rules = [_parse_rule(item, family_id, index + 1) for index, item in enumerate(rules_data)]
        labels = [rule.label for rule in rules]
        for label in labels:
            if labels.count(label) > 1:
                _fail(where, "two rules have the label '%s'." % label)
        return Family(family_id, title, mode, max_per_1000, strategy, delete_ok, rules=rules, note=note)
    _check_params(mapping["check"], mapping.get("params"), where)
    return Family(family_id, title, mode, max_per_1000, strategy, delete_ok, check=mapping["check"],
                  params=mapping["params"], tier=_tier(mapping, where), sources=_sources(mapping, where),
                  note=note)


def parse_data(data):
    """Check the parsed data file and return a Patterns object. Raise PatternError."""
    if not isinstance(data, dict):
        raise PatternError("The pattern data must be a mapping.")
    for key in data:
        if key not in _DATA_KEYS:
            raise PatternError("The pattern data holds the unknown key '%s'." % key)
    if data.get("version") != 1:
        raise PatternError("The pattern data must have 'version' 1.")
    as_of = data.get("as_of")
    if not isinstance(as_of, str) or not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", as_of):
        raise PatternError("The pattern data needs 'as_of' as a date, such as 2026-10-23.")
    families_data = data.get("families")
    if not isinstance(families_data, list) or not families_data:
        raise PatternError("The pattern data needs a non-empty list 'families'.")
    families, seen = [], set()
    for index, item in enumerate(families_data):
        family = _parse_family(item, index + 1)
        if family.id in seen:
            raise PatternError("Family '%s': the id is used twice." % family.id)
        seen.add(family.id)
        families.append(family)
    return Patterns(families, as_of)


# ---------------------------------------------------------------------------------------
# The project file
# ---------------------------------------------------------------------------------------

def _apply_override(family, spec, file_name):
    where = "Project file '%s', family '%s'" % (file_name, family.id)
    if not isinstance(spec, dict):
        _fail(where, "the value must be a mapping of keys.")
    _check_keys(spec, _OVERRIDE_KEYS, where, "family")
    changed = copy.copy(family)
    if "enabled" in spec:
        if not isinstance(spec["enabled"], bool):
            _fail(where, "'enabled' must be true or false.")
        changed.enabled = spec["enabled"]
    if "mode" in spec:
        if spec["mode"] not in MODES:
            _fail(where, "'mode' must be each or density, not %r." % (spec["mode"],))
        if family.check is not None:
            _fail(where, "a structural family keeps its mode, so 'mode' changes nothing.")
        if spec["mode"] == family.mode:
            _fail(where, "the family is already in %s mode, so 'mode' changes nothing." % family.mode)
        changed.mode = spec["mode"]
    if "max_per_1000" in spec:
        if not _is_number(spec["max_per_1000"]) or spec["max_per_1000"] <= 0:
            _fail(where, "'max_per_1000' must be a number above zero.")
        if changed.mode != "density":
            _fail(where, "'max_per_1000' changes nothing in each mode. Set 'mode: density' too.")
        changed.max_per_1000 = spec["max_per_1000"]
    if changed.mode == "density" and changed.max_per_1000 is None:
        _fail(where, "the family is in density mode and needs 'max_per_1000'.")
    if "disable_labels" in spec:
        labels = spec["disable_labels"]
        valid = [rule.label for rule in family.rules]
        if not isinstance(labels, list) or not labels or not all(isinstance(x, str) for x in labels):
            _fail(where, "'disable_labels' must be a non-empty list of rule labels.")
        if not valid:
            _fail(where, "a structural family has no rules, so 'disable_labels' changes nothing.")
        for label in labels:
            if label not in valid:
                _fail(where, "the rule label %r is unknown. The valid labels are %s." % (label, ", ".join(valid)))
        if len(set(labels)) != len(labels):
            _fail(where, "'disable_labels' names a label twice.")
        if len(labels) == len(valid):
            _fail(where, "'disable_labels' would turn off every rule. Use 'enabled: false' instead.")
        changed.rules = [rule for rule in family.rules if rule.label not in labels]
        changed.disabled_rules = family.disabled_rules + [rule for rule in family.rules if rule.label in labels]
    return changed


def _extra_family(item, number, file_name, taken):
    prefix = "Project file '%s', extra pattern" % file_name
    if not isinstance(item, dict):
        _fail("Project file '%s'" % file_name, "'extra_patterns' item number %d must be a mapping." % number)
    pattern_id = item.get("id")
    if not isinstance(pattern_id, str) or not _ID.match(pattern_id):
        _fail(prefix + " number %d" % number, "the id %r must use lower-case letters, digits and hyphens." % (pattern_id,))
    where = "%s '%s'" % (prefix, pattern_id)
    if pattern_id in taken:
        _fail(where, "the id is already in use.")
    _check_keys(item, _EXTRA_KEYS, where, "extra pattern")
    title = _text(item, "title", where)
    strategy = _text(item, "strategy", where)
    mode = item.get("mode", "each")
    if mode not in MODES:
        _fail(where, "'mode' must be each or density, not %r." % (mode,))
    max_per_1000 = item.get("max_per_1000")
    if max_per_1000 is not None and (not _is_number(max_per_1000) or max_per_1000 <= 0):
        _fail(where, "'max_per_1000' must be a number above zero.")
    if mode == "density" and max_per_1000 is None:
        _fail(where, "a density pattern needs 'max_per_1000'.")
    regex, words, unless = _parse_pattern(item, False, where)
    rule = Rule("T3", ["project:" + file_name], title, regex, words, unless)
    return Family(pattern_id, title, mode, max_per_1000, strategy, False, rules=[rule])


def apply_project(patterns, project, file_name=PROJECT_FILE_NAME):
    """Return new Patterns with the project settings merged. The input stays unchanged."""
    prefix = "Project file '%s'" % file_name
    if project is None:
        project = {}
    if not isinstance(project, dict):
        raise PatternError("%s: the top level must be a mapping." % prefix)
    _check_keys(project, _PROJECT_KEYS, prefix, "top-level")
    overrides = project.get("families")
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise PatternError("%s: 'families' must be a mapping of family ids." % prefix)
    known = OrderedDict((family.id, family) for family in patterns.families + patterns.disabled)
    for family_id in overrides:
        if family_id not in known:
            raise PatternError("%s: the family id '%s' is unknown. The valid ids are %s." % (
                prefix, family_id, ", ".join(known)))
    merged = OrderedDict()
    for family_id, family in known.items():
        if family_id in overrides:
            family = _apply_override(family, overrides[family_id], file_name)
        merged[family_id] = family
    extras = project.get("extra_patterns")
    if extras is None:
        extras = []
    if not isinstance(extras, list):
        raise PatternError("%s: 'extra_patterns' must be a list." % prefix)
    for number, item in enumerate(extras, 1):
        extra = _extra_family(item, number, file_name, merged)
        merged[extra.id] = extra
    return Patterns([f for f in merged.values() if f.enabled], patterns.as_of,
                    [f for f in merged.values() if not f.enabled])
