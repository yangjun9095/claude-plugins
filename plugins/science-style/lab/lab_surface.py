"""The surface layer (spec section 11): measures of each paper by script, pooled per person.

Methods text never counts. The passive measure is an estimate: a form of "be", an optional adverb
in -ly, and a past participle (a word in -ed or a listed irregular form). The pilot measures its
precision. Distinctive vocabulary uses the log-odds ratio with an informative Dirichlet prior
(Monroe, Colaresi and Quinn, 2008), each person against the others, on words that at least
MIN_PEOPLE people use.
"""
import math
import os
import re
import string
from collections import Counter

from lab_paths import PLUGIN_ROOT, read_json
from lab_text import iter_paragraphs, split_sentences, words

WORDLISTS_PATH = os.path.join(PLUGIN_ROOT, "data", "wordlists.json")
MIN_PEOPLE = 4
TOP_WORDS = 30
TOP_PAIRS = 20
FIRST_PERSON = re.compile(r"\b(?:[Ww]e|[Oo]ur|[Oo]urs|us|[Mm]y)\b")
FIGREF = re.compile(r"\b(?:Extended Data |Supplementary )?(?:Fig(?:ure)?s?\.?|Tables?)\s*S?\d", re.I)
BARE_I = re.compile(r"\bI\b(?![-\d])(?!\s+I\b)")
ROMAN_CONTEXT = frozenset("""type class phase complex group stage grade part site domain region photosystem
chapter section table figure fig appendix level set""".split())
_EDGE_MARKS = string.punctuation + "“”‘’"
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?")
QUESTION_END = re.compile(r"\?[\"')\]”’]*$")


def load_wordlists(path=WORDLISTS_PATH):
    return read_json(path)


def passive_pattern(irregular):
    """Return the passive pattern. A regular participle has at least two letters before "-ed", so
    "is red" does not match, and "indeed" is not a participle."""
    forms = "|".join(sorted((re.escape(w) for w in irregular), key=len, reverse=True))
    return re.compile(r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?"
                      r"(?:(?!indeed\b)\w{2,}ed|" + forms + r")\b", re.I)


def has_first_person(sentence):
    """Return True when the sentence has a first-person word.

    A bare "I" counts unless it is a roman numeral. The "I" is a roman numeral when "-", a digit or
    another "I" follows it, or when a word of ROMAN_CONTEXT, such as "Type", comes before it. A comma,
    semicolon or colon after that word ends the context, so "In this section, I show" counts.
    """
    if FIRST_PERSON.search(sentence):
        return True
    for match in BARE_I.finditer(sentence):
        before = sentence[:match.start()].split()
        previous = before[-1] if before else ""
        if previous[-1:] in (",", ";", ":") or previous.strip(_EDGE_MARKS).lower() not in ROMAN_CONTEXT:
            return True
    return False


def top(counter, n):
    """Return the n most common entries as [key, count], ties broken by key."""
    return [[key, count] for key, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def collect(paper):
    """Return the sentences (with their kind) and the sentences per paragraph, Methods left out."""
    sentences, sizes = [], []
    for kind, _, paragraph in iter_paragraphs(paper):
        found = split_sentences(paragraph)
        sizes.append(len(found))
        sentences.extend((kind, s) for s in found)
    return {"sentences": sentences, "paragraph_sizes": sizes}


def merge(collected):
    out = {"sentences": [], "paragraph_sizes": []}
    for item in collected:
        out["sentences"].extend(item["sentences"])
        out["paragraph_sizes"].extend(item["paragraph_sizes"])
    return out


def stats(values):
    """Return the mean, median, 90th percentile (nearest rank) and count of values."""
    if not values:
        return {"mean": 0.0, "median": 0.0, "p90": 0.0, "n": 0}
    ordered = sorted(values)
    n = len(ordered)
    median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
    p90 = ordered[max(0, int(math.ceil(0.9 * n)) - 1)]
    return {"mean": round(sum(ordered) / float(n), 2), "median": float(median), "p90": float(p90), "n": n}


def measures(collected, wordlists):
    """Return the surface measures of spec section 11 for collected sentences."""
    hedges = set(wordlists["hedges"])
    connectives = set(wordlists["connectives"])
    passive = passive_pattern(wordlists["irregular_participles"])
    lengths, by_kind = [], {}
    hedge_counts, connective_counts, openers, opener_pairs = Counter(), Counter(), Counter(), Counter()
    total = first = passives = questions = numbers = citations = figures = 0
    for kind, sentence in collected["sentences"]:
        tokens = words(sentence)
        lower = [t.lower() for t in tokens]
        total += len(tokens)
        lengths.append(len(tokens))
        by_kind.setdefault(kind, []).append(len(tokens))
        hedge_counts.update(t for t in lower if t in hedges)
        connective_counts.update(t for t in lower if t in connectives)
        if lower:
            openers[lower[0]] += 1
        if len(lower) > 1:
            opener_pairs[lower[0] + " " + lower[1]] += 1
        first += 1 if has_first_person(sentence) else 0
        passives += 1 if passive.search(sentence) else 0
        questions += 1 if QUESTION_END.search(sentence) else 0
        numbers += len(NUMBER.findall(sentence))
        citations += sentence.count("[CIT]")
        figures += len(FIGREF.findall(sentence))
    n = len(collected["sentences"])
    paragraphs = len(collected["paragraph_sizes"])

    def per_sentence(count):
        return round(count / float(n), 3) if n else 0.0

    def per_1000(count):
        return round(1000.0 * count / total, 2) if total else 0.0

    return {
        "n_sentences": n, "n_words": total, "n_paragraphs": paragraphs,
        "sentence_length": stats(lengths),
        "sentence_length_by_kind": {kind: stats(v) for kind, v in sorted(by_kind.items())},
        "paragraph_sentences": stats(collected["paragraph_sizes"]),
        "first_person_share": per_sentence(first),
        "passive_share": per_sentence(passives),
        "hedges_per_1000": per_1000(sum(hedge_counts.values())),
        "hedge_words": top(hedge_counts, 50),
        "connectives_per_1000": [[w, per_1000(c)] for w, c in top(connective_counts, 50)],
        "questions_per_100": round(100.0 * questions / n, 2) if n else 0.0,
        "numbers_per_sentence": per_sentence(numbers),
        "citations_per_sentence": per_sentence(citations),
        "figure_refs_per_paragraph": round(figures / float(paragraphs), 3) if paragraphs else 0.0,
        "openers": top(openers, 15),
        "opener_pairs": top(opener_pairs, 10),
    }


def vocab_counts(collected):
    """Return the word counts and the word-pair counts of collected sentences. Numbers are left out."""
    unigrams, bigrams = Counter(), Counter()
    for _, sentence in collected["sentences"]:
        lower = [w.lower() for w in words(sentence) if not w[0].isdigit()]
        unigrams.update(lower)
        bigrams.update(a + " " + b for a, b in zip(lower, lower[1:]))
    return unigrams, bigrams


def log_odds_z(counts_a, counts_b, prior):
    """Return the z-score of the log-odds ratio of each prior word, group a against group b."""
    n_a = sum(counts_a.values())
    n_b = sum(counts_b.values())
    a0 = sum(prior.values())
    z = {}
    for word, alpha in prior.items():
        ya, yb = counts_a.get(word, 0), counts_b.get(word, 0)
        delta = (math.log((ya + alpha) / float(n_a + a0 - ya - alpha))
                 - math.log((yb + alpha) / float(n_b + a0 - yb - alpha)))
        z[word] = delta / math.sqrt(1.0 / (ya + alpha) + 1.0 / (yb + alpha))
    return z


def distinctive(person_counts, min_people=MIN_PEOPLE, top_n=TOP_WORDS):
    """Return the top_n words of each person by z-score, or {} with fewer than min_people people.
    With fewer than 2 shared words, return an empty list for each person."""
    if len(person_counts) < min_people:
        return {}
    presence = Counter()
    for counts in person_counts.values():
        presence.update(set(counts))
    shared = {w for w, k in presence.items() if k >= min_people}
    if len(shared) < 2:
        return {person: [] for person in person_counts}
    total = Counter()
    for counts in person_counts.values():
        total.update({w: n for w, n in counts.items() if w in shared})
    out = {}
    for person, counts in person_counts.items():
        mine = Counter({w: n for w, n in counts.items() if w in shared})
        z = log_odds_z(mine, total - mine, total)
        ranked = sorted(z.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
        out[person] = [[w, round(v, 2)] for w, v in ranked]
    return out


def run_surface(papers_by_person, wordlists):
    """Return the surface data of every person in papers_by_person ({person: [paper files]})."""
    out, unigrams, bigrams = {}, {}, {}
    for person, papers in sorted(papers_by_person.items()):
        collected = [collect(p) for p in papers]
        pooled = merge(collected)
        out[person] = {"n_papers": len(papers), "pooled": measures(pooled, wordlists),
                       "per_paper": {p["work_id"]: measures(c, wordlists) for p, c in zip(papers, collected)}}
        unigrams[person], bigrams[person] = vocab_counts(pooled)
    words_z = distinctive(unigrams, top_n=TOP_WORDS)
    pairs_z = distinctive(bigrams, top_n=TOP_PAIRS)
    notes = []
    if not words_z:
        notes.append("needs at least {} people".format(MIN_PEOPLE))
    else:
        if not any(words_z.values()):
            notes.append("fewer than 2 words shared by {} people".format(MIN_PEOPLE))
        if not any(pairs_z.values()):
            notes.append("fewer than 2 pairs shared by {} people".format(MIN_PEOPLE))
    for person in out:
        out[person]["distinctive_words"] = words_z.get(person, [])
        out[person]["distinctive_pairs"] = pairs_z.get(person, [])
        out[person]["distinctive_note"] = "; ".join(notes)
    return out
