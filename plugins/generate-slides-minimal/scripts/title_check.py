"""Title checks of the design linter: a topic label, the word count and a verb heuristic.

This module reads plain text. It imports no pptx code. `title_problem()` returns the message
of the first problem of a title, or None.

The verb check has no part-of-speech tagger. It uses two word lists and the words around a word.
  - A verb that is rarely a noun (precede, tune, withhold) counts as a verb in its base and -s forms.
  - A word that is often a noun too (design, control, test, map) counts only when a determiner,
    a number or an adverb follows it, as in "sets the pace" and "cost 41 units". A number is a word or digits.
    A short list of intransitive verbs of this kind (run, spread, drop, fall) also counts in its -s form
    after a noun and before a preposition: "runs in an hour".
  - A past form counts after a noun, before a preposition, before a coordinator and at the end of the title:
    "Latency fell by half". A past form is an irregular form of a short list (fell, rose, ran), or an -ed word
    of 4 letters or more. A short list of nouns and adjectives in -ed (sacred, naked, indeed) holds the exceptions.
  - A past form or an -ing word does not count in first place, after a determiner, after a preposition
    or after an adverb. An -ing word counts only before a determiner, a preposition or an adverb.
  - An unknown word that ends in -s and stands before a determiner counts as a verb.
The check can miss a verb that is not in the lists. Its message says "no verb that this check knows".

Limits. The check is a T3 heuristic with a closed verb list. It has no way to read a sentence.
  - A past form counts before a preposition. A past form cannot be told from a participle in a reduced
    relative clause, so a noun phrase with a participle passes. "Genes expressed in the liver" has a verb for
    this check, as "The comet brightened within a week" has.
  - Some irregular past forms are common nouns too: bound, felt, left, rose, saw, shot, spoke, thought, won.
    After a noun or an adjective they count as a verb. So "A lower bound on the error rate", "Flu shot uptake"
    and "Wild rose genome" pass. An acronym in lower case can match too, as led (LED) does.
  - A word of 3 letters in -ed (fed, wed) is not a past form. A noun or an adjective in -ed that the short list
    does not name counts as a verb: sled, testbed, seabed. So "Rocket sled tests" passes.
  - Set, split and spread have the same form in the present and the past. They count only by the homograph
    rules: "Gene set enrichment" is flagged, and "The team set a record" passes. So the check misses the past
    form of spread before a preposition without a homograph cue. Split has the same miss: "The committee split
    over the budget" gets the warning.
  - A noun phrase of the shape noun + intransitive verb form + preposition cannot be told apart from a
    sentence. "Recent changes in policy" and "Major gains in accuracy" are noun phrases, and both pass.
  - A homograph after a noun and before digits counts as a verb. So "Patient group 3 and the control group" passes.
  - A past form after a determiner does not count, and the lists hold "more" as a determiner. So "Every design
    with an Osprey score of 9 or more gave a signal above 60 au" gets the warning.
  - A title can warn wrongly or pass wrongly. The author decides.
The tests measure the check on made-up titles in seven corpora. Corpora A to E have two bars. At most 8 percent of
the sentences are flagged, and at least 70 percent of the noun phrases. The rates of corpus D are an estimate for
present-tense titles written by the author of the rules. Corpus F holds past-tense titles. Its only bar is
10 percent false alarms on the sentences, and its noun-phrase rate has no bar. Corpus G holds titles with set, split
and spread. Its bars are 90 percent of the noun phrases flagged, and 75 percent of the sentences passed.
"""
import re

# The functions is_topic_label() and is_sentence() follow generate-slides v1 (scripts/verify_slides.py,
# `_is_topic_label` and `_is_sentence`), same author, MIT. The verb check is an extension: v1 only counted words.
TOPIC_LABEL_PATTERNS = [
    r"^results?$", r"^methods?$", r"^background$", r"^introduction$",
    r"^discussion$", r"^overview$", r"^summary$", r"^conclusions?$",
    r"^motivation$", r"^outline$", r"^agenda$", r"^objectives?$",
    r"^approach$", r"^next steps$", r"^future work$",
    r"^data$", r"^analysis$", r"^evaluation$", r"^implementation$",
    r"^model performance$", r"^experimental setup$",
]

# Verbs that are rarely nouns.
_VERBS = """
abandon abide abolish abort absorb accelerate accept accommodate accompany accomplish accrue accumulate accuse
achieve acknowledge acquire activate adapt add adhere adjust administer admit adopt advance advocate affect
afford agree aid alert align alleviate allocate allow allude alter amass amend amplify analyze anchor anneal
annotate anticipate appear append apply appreciate approximate arise arrange arrest arrive articulate ascend ask
aspire assemble assert assess assign assimilate assist associate assume assure attach attain attend attenuate
attract attribute audit augment authorize automate avert avoid await awaken balance ban beat become begin behave
believe belong bend bestow betray bind bleach blend blunt blur boast bolster boost borrow bounce break breed
brighten bring broaden buffer build burn bury buy bypass calculate calibrate cancel cap capture carry carve
catalyze categorize cause cease characterize chase choose circulate cite clarify classify click coax coincide
collaborate collapse collect collide combine come comfort commence commit communicate compare compel compensate
compete compile complain complement complete complicate comply compose comprehend compress comprise compute
conceal concede conceive concentrate conclude concur condemn condense conduct confer confine confirm conform
confound confront connect conserve consider consist constitute constrain construct consult consume contain
contaminate contend continue contradict contribute converge convert convey convince cooperate coordinate cope
copy correct correlate correspond corrupt counter create crush cultivate curb curtail customize dampen decay
decide decipher declare decode decompose decouple dedicate deduce deem deepen defeat defend defer define deflect
deform defy degrade delete delineate deliver demonstrate denote deny depend depict deplete deploy deposit
deprive derive descend describe deserve designate destabilize destroy detach detect deter deteriorate determine
develop deviate devise devote diagnose dictate die differ differentiate diffuse dilute dim diminish direct
disagree disappear discard disclose disconnect discourage discover discuss dismiss disperse displace dispute
disrupt dissociate dissolve distinguish distort distract distribute disturb diverge diversify divide document
dominate donate drag drain drift drown dump duplicate dwarf earn ease eat echo educate elaborate elevate elicit
eliminate embed embrace emerge emit emphasize employ empower emulate enable encode encompass encounter encourage
endorse endure enforce engage engineer enhance enjoy enlarge enrich ensure entail entangle enter envision equal
equate equip eradicate erase erode escape establish evade evaluate evaporate evoke evolve exacerbate exaggerate
excavate exceed excel excite exclude execute exert exhaust exhibit exist expand expect expedite expel explain
exploit explore expose express extend extinguish extract fabricate facilitate fade fail falter fascinate favor
feed feel fetch fight fill filter find finish fix flag flank flatten flee flicker flip float flood flourish
fluctuate fly fold follow forbid force forecast foresee forge forget formulate forward foster fragment freeze
frustrate fuel fulfill fuse gather gauge generalize generate get give glide glow go govern grab grade grant
grasp grow guarantee guard halve hammer hamper happen harbor harm harness harvest hasten hate have heal hear
heighten help hesitate hide highlight hinder hinge hire hover hunt hurt hybridize hypothesize identify ignite
ignore illuminate illustrate imagine imitate immerse impair impart impede implement implicate imply impose
impress improve incorporate incubate indicate induce infect infer inflate inflict inform ingest inherit inhibit
initiate inject innovate insert insist inspect inspire install instruct insulate integrate intend intensify
interact intercept interfere interpret interrupt intersect intervene introduce invade invert invest investigate
invite invoke involve isolate jeopardize join judge jump justify keep kill kindle know lag last lean learn leave
lend lessen let lie linger listen localize locate loosen lose lower lure magnify maintain make manage manifest
manipulate mask master matter mature maximize mediate meet melt mend merge merit migrate mimic minimize mirror
mislead miss mitigate mobilize mock moderate modify modulate monitor motivate mourn multiply mutate navigate
necessitate neglect negotiate neutralize normalize nourish nudge nurture obey obscure observe obstruct obtain
occupy occur omit operate oppose optimize organize orient originate oscillate outcompete outgrow outlive
outnumber outpace outperform outweigh overcome overexpress overlook override oversee overshadow overwhelm owe
own parallel participate partition penalize penetrate perceive perform permit persist persuade perturb pervade
phosphorylate pierce pinpoint pioneer plague plunge polarize ponder portray possess postulate pour practice
praise precede precipitate predict predispose prefer prepare prescribe present preserve presume pretend prevent
prioritize probe proclaim produce progress prohibit prolong promote prompt propagate propel propose prosper
protect prove provide provoke prune publish pull punish pursue push put qualify quantify quench quote raise
react realize rebalance rebound rebuild recede receive reckon reclaim recognize recommend reconcile reconstruct
recover recruit rectify recur recycle redirect reduce refer refine reflect refrain refute regain regard
regenerate regulate reinforce reject relate relax rely remain remember remove render renew reopen repeat repel
replace replenish represent repress reproduce require rescue resemble reserve reside resist resolve resonate
respond restore restrain restrict resume resurface retain retard retreat retrieve reuse reveal reverse revise
revive revolve rewire rinse roam rotate rupture rush sanction satisfy saturate save say scatter scrutinize seal
secure seek seem seep seize select sell send separate serve settle shake sharpen shatter shed shield shock
shorten shout show shrink shut sift signify silence simplify simulate sink sit skew skip slide slip smash snap
soak soar solve soothe spark spawn speak specify spend spin splash spoil spray sprout spur squeeze stabilize
steep steer stimulate stir stop stratify strengthen strip strive stumble stun subdivide submit subside
substitute subtract succeed suffer suffice suggest summarize supplement suppose suppress surge surpass surrender
surround survive suspect suspend sustain swallow swarm sway sweep swell synthesize tackle take tame taper
tarnish teach tease tell tempt tend terminate testify thank thaw thicken think thread threaten thrive tighten
tilt toggle tolerate trail transcend transcribe transfer transform translate transmit traverse treat tremble
trickle try tune uncover undercut underestimate undergo underlie undermine underscore understand undertake undo
unfold unify unleash unlock unravel unveil uphold upregulate urge utter validate vanish vary veer venture verify
vibrate vindicate violate visualize wade wander wane want warn warrant weaken wear weave weigh widen wield wilt
win wipe withdraw wither withhold withstand witness wonder worsen wound wreck write yearn
"""

# Verbs that are often nouns too. They count only in the context that the module docstring gives.
_HOMOGRAPHS = """
act address age aim answer approach attack attempt average back base bear benefit bias block bond bound branch
bridge bundle call case cast center challenge change charge check claim clean clear clone close cluster conflict
contact contrast control cost count couple cover crash cross cure curve cut damage deal debate decline decrease
delay demand design desire display dose double doubt draw drive drop dwell edit end estimate exchange experience
experiment export face fall fear feature field figure fit flow focus form frame free function gain group guess
guide halt handle head heat hit hold hope host image impact import increase influence input interest issue key
label lack land launch lead leak level lift light limit link list live load lock log look loss map mark match
mean measure mention mix model mount move name narrow need note notice object offer open order output overlap
pace pack pair part pass pattern pause pay peak pick place plan play plot point pool pose position post power
press price print process profile program project proof query question race rank rate reach read reason recall
record release repair replicate report request resource response rest result return review reward rise risk role
round route rule run sample scale scan schedule score screen search seed sense sequence set shape share shift
sign signal site size skill slow smooth sort sound source span spare speed spike split spot spread stack stage
stain stall stand start state stem step stock strain stream stress stretch strike structure study subject suit
sum supply support surface survey swap switch tag talk target task team term test text tie time total touch
track trade train transport trap trend trial trigger trim trust turn type update upgrade use value view visit
wait walk wash waste watch wave way welcome work wrap yield zoom
"""

# Homograph verbs that need no object, so that a preposition follows them: "the pipeline runs in an hour".
# The -s form of these counts after a singular noun and before a preposition. The list holds the verbs by name,
# because the same shape is a noun phrase for most other words. "Cell maps of the heart" needs "of", which is left out below.
_INTRANSITIVE = """
run spread drop fall rise split change shift peak rest track cluster form link rank score match group map cut gain
decline increase decrease light
"""

_IRREGULAR_PAST = """
took gave saw grew fell drove ran held kept lost began chose led met sat stood told thought brought built got
spoke wrote became felt left sent spent broke threw won said paid knew went made found bound shown taken given
seen known grown fallen driven chosen begun written broken thrown beaten spoken
rose drew shot shrank slept ate
"""

# Nouns and adjectives of 4 letters or more that end in -ed. They are no past forms. The lists read the words need,
# seed, feed and speed as present forms, and hundred is a number, so they need no entry here.
_NOT_PAST = frozenset("""
sacred naked wicked indeed weed deed reed heed creed greed bleed proceed kindred hatred
""".split())

_AUXILIARIES = frozenset("""
is are was were be been being am has have had having do does did can could will would shall should may might must
""".split())

# Words that start a noun phrase, and numbers.
_DETERMINERS = frozenset("""
the a an this that these those its their our his her my your each every all both no any some most more less fewer
many few several such another other it them us him itself themselves
one two three four five six seven eight nine ten eleven twelve fifteen twenty thirty fifty hundred
""".split())

_PREPOSITIONS = frozenset("""
of in on at by for with from to into onto over under across between among within without about after before
during through per via than as up off out near beyond against along around behind below beside despite except
like inside outside since toward towards until upon amid atop
""".split())

_COORDINATORS = frozenset("and or but nor yet so".split())
_CONJUNCTIONS = _COORDINATORS | frozenset("""
because although whereas while whether if when where which who whom whose how what why then thus unless once
""".split())

# A word after one of these is in a noun position: an adjective, a noun or a reduced clause.
_NOUN_CUES = _DETERMINERS | _PREPOSITIONS | frozenset("first second third last next new old same early late".split())
_ADVERBS = frozenset("not also still never always often well much only just even already".split())
_OPENERS = _DETERMINERS | _ADVERBS


def _forms(base):
    """Return the spellings of a regular verb: base, -s, -es, -ed, -ing and the doubled endings."""
    forms = {base, base + "s", base + "es", base + "ed", base + "ing", base + base[-1] + "ed", base + base[-1] + "ing"}
    if base.endswith("e"):
        forms |= {base + "d", base[:-1] + "ing"}
    if base.endswith("y") and base[-2:-1] not in ("a", "e", "i", "o", "u"):
        forms |= {base[:-1] + "ies", base[:-1] + "ied"}
    if base.endswith("ie"):
        forms.add(base[:-2] + "ying")
    return forms


def _kind(word, base):
    """Return "present", "past" or "ing" for a form of `base`."""
    if word.endswith("ing") and word != base:
        return "ing"
    if word.endswith("ed") and word != base:
        return "past"
    return "present"


# word -> (is a homograph, kind, is the base form). A word in both lists counts as a plain verb.
_FORMS = {}
for _list, _homograph in ((_HOMOGRAPHS, True), (_VERBS, False)):
    for _base in _list.split():
        for _form in _forms(_base):
            _FORMS[_form] = (_homograph, _kind(_form, _base), _form == _base)
for _form in _IRREGULAR_PAST.split():
    _FORMS[_form] = (False, "past", False)

_WORD = re.compile(r"[^\W_]+")


def is_topic_label(title):
    """Check if a title looks like a topic label instead of a sentence."""
    t = title.strip().rstrip(".!?").lower()
    for pat in TOPIC_LABEL_PATTERNS:
        if re.match(pat, t, re.IGNORECASE):
            return True
    return False


def _is_adverb(word):
    return word in _ADVERBS or (len(word) > 3 and word.endswith("ly"))


def _plural(word):
    """Return True for a word that looks like a plural noun: it ends in -s but not in -ss, -us, -is, -ics, -ous."""
    return word.endswith("s") and not word.endswith(("ss", "us", "is", "ics", "ous"))


# A noun in the plural takes "of", "for", "about", "per", "between" and "than": "changes in" is ambiguous, "maps of" is not.
_AFTER_VERB = _PREPOSITIONS - frozenset("of for about per between than".split())
_INTRANSITIVE_S = frozenset(form for base in _INTRANSITIVE.split() for form in _forms(base) if form != base)

_FUNCTION_WORDS = _DETERMINERS | _PREPOSITIONS | _CONJUNCTIONS | _ADVERBS | _AUXILIARIES


def _verb_at(words, index):
    """Return True when the word at `index` acts as a verb in its place in the title."""
    word = words[index]
    previous = words[index - 1] if index else ""
    following = words[index + 1] if index + 1 < len(words) else ""
    if word in _AUXILIARIES:
        return True
    # A singular noun before the word, and a noun, an adjective or a determiner after it: "score tracks ratings".
    singular_before = bool(previous) and previous not in _FUNCTION_WORDS and not _plural(previous)
    object_after = bool(following) and following not in _PREPOSITIONS | _COORDINATORS
    after_noun_cue = previous in _DETERMINERS | _PREPOSITIONS
    # A past form stands after a noun or a verb, never in first place, after a determiner, a preposition or an adverb.
    past_place = bool(index) and previous not in _NOUN_CUES and not _is_adverb(previous)
    entry = _FORMS.get(word)
    if entry is None:
        if word in _FUNCTION_WORDS or word in _NOUN_CUES or not index:
            return False
        if len(word) >= 6 and word.endswith(("izes", "ises", "ifies")):
            return True
        if len(word) >= 4 and word.endswith("ed") and word not in _NOT_PAST:
            entry = (False, "past", False)
        elif len(word) >= 6 and word.endswith("ing"):
            entry = (False, "ing", False)
        elif _plural(word):  # an unknown word in -s: "masks real differences", but not "datasets used in"
            return len(word) >= 4 and singular_before and object_after
        else:  # an unknown base form after a plural subject and before a determiner: "doses elicit a response"
            return _plural(previous) and following in _DETERMINERS
    homograph, kind, bare = entry
    if kind == "past":
        return past_place
    if kind == "ing":
        return bool(index) and not after_noun_cue and not _is_adverb(previous) and (
            following in _OPENERS | _PREPOSITIONS or _is_adverb(following))
    if not index:
        return False
    if not homograph:  # a plain verb after "to" is an infinitive: "things to remember"
        return not (after_noun_cue and previous != "to")
    if after_noun_cue:
        return False
    if following in _OPENERS or following.isdigit() or _is_adverb(following):  # "cost three units", "cost 41 units"
        return True
    if bare:
        return _plural(previous)
    return singular_before and (object_after or (word in _INTRANSITIVE_S and following in _AFTER_VERB))


def has_verb(title):
    """Return True when a word of the title acts as a verb. See the module docstring for the rules."""
    words = _WORD.findall(title.lower())
    return any(_verb_at(words, index) for index in range(len(words)))


def is_sentence(title):
    """A sentence has at least two words and a verb. v1 counted words only."""
    return len(title.split()) >= 2 and has_verb(title)


def title_problem(text, low, high):
    """Return the message for the first problem of a title, or None when the title passes.

    The checks run in this order: a topic label, a word count outside low to high, no known verb.
    """
    count = len(text.split())
    if is_topic_label(text):
        return "the title looks like a topic label; write a sentence that states the claim"
    if not low <= count <= high:
        return "the title has {} words; use {} to {} words".format(count, low, high)
    if not is_sentence(text):
        return ("the title has no verb that this check knows. Use a plain verb, "
                "or ignore this warning if the title is a sentence.")
    return None
