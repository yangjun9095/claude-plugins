"""Tests for scripts/title_check.py: topic labels, the word count and the verb heuristic.

The corpus tests measure the verb heuristic on made-up titles. A sentence title that the check flags
with "no verb" is a false alarm. A noun phrase that the check passes is a miss. All titles are made up.
"""
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import title_check  # noqa: E402

# Corpus A. I wrote these titles first, from verbs that I chose, and measured the check on them.
SENTENCES_A = """
Heat stress amplifies the response of most stress genes
Low oxygen attenuates growth in every strain we tested
Extra replicates bolster confidence in the weakest peaks
A second enzyme buffers the loss of the first
The new protocol bypasses the need for a separate wash step
Mutant lines compensate for the missing receptor within days
Signal concentrates at the edge of the tissue
Expression of the two genes correlates across all samples
Strict filters curb false positives at a small cost in recall
Our split decouples training data from the test cohort
Starvation depletes the pool of free amino acids
Closely related species diverge in their promoter usage
The assay enriches rare variants more than the standard method
Tumor cells evade the immune response through loss of the antigen
Noise fluctuates with the time of day in the raw traces
Small clones harbor most of the rare mutations
Shorter reads impair the assembly of repeat regions
Retinoic acid induces the marker in a dose dependent way
Two kinases interfere with each other at high doses
Most hits localize to the nuclear envelope
The synthetic peptide mimics the natural ligand at low cost
Hormone levels modulate the timing of the first division
Healthy samples outnumber diseased ones by a factor of three
Small perturbations reshape the landscape of open chromatin
A recurrent network reconstructs the missing frames from context
Early dosing rescues the phenotype in treated larvae
Cold exposure retards development by about a day
Large batches saturate the sequencer well before the run ends
Careful normalization sharpens the contrast between the two groups
A single mutation stabilizes the fold at room temperature
Training stalls when the learning rate is too high
Light pulses stimulate branching in the root tip
The gene family subdivides into three clades with distinct motifs
Cells in the center sustain the signal for several hours
A short peptide tunes the stability of the complex
All treated animals undergo a rapid change in weight
Early transcription factors underlie the shift in cell fate
Background noise vanishes after the second filtering step
The reviewers withhold judgment until the replicate arrives
Pooled screens yield more hits per dollar than arrayed screens
Lower temperatures slow the rate of protein turnover
Methylation silences the promoter in the late embryo
We observe a sharp drop in coverage near the centromere
Samples from site B group apart from the other two sites
Mixed cultures outgrow the pure line within a week
Both antibodies recognize the same epitope
Older mice carry more damaged mitochondria
Counts grow with depth up to a ceiling
The score tracks expert ratings across all five panels
Calibration removes most of the bias in the raw scores
""".strip().split("\n")

NOUN_PHRASES_A = """
Chromatin accessibility maps of the developing heart
A catalog of enhancers active in the first two days
Statistical power for the planned pilot study
Dose response curves for the three lead compounds
Sampling strategy and sample sizes for each cohort
Variant calling pipeline for low coverage genomes
Differences between the old and the new protocol
Timeline and budget for the next phase of the project
Expression atlas of the zebrafish tailbud
Benchmark datasets used in the comparison
Open questions about the role of the second enhancer
Reference genome and annotation versions for all species
Cell counts per cluster and per timepoint
Data sources and processing steps for the figures
Single cell resolution of the embryonic gut
Candidate regulators of the late heart program
Comparison of three normalization methods on pooled samples
Training data and test splits for the classifier
Background on the assay and its main limitations
Plan for the validation experiments in the second year
Examples of failed designs and their sequence features
Marker genes of the nine major cell populations
The experimental setup for the knockdown series
Pairwise correlations between replicates of the time course
Taxonomy of lineage tracing tools in current use
""".strip().split("\n")

# Corpus B. I wrote these after the lists of title_check.py were final, from other verbs, and measured the check once.
SENTENCES_B = """
Dropout inflates the apparent difference between neighboring clusters
The new filter blunts the effect of ambient RNA
Imputation masks real differences in rare cell types
Higher doses elicit a stronger response in the late stage
Large language models rarely refute their own earlier claims
Warmer water accelerates the pace of development in fish
Enhancer deletions erode the expression of nearby genes
Our estimates mirror the published values within error
A single probe pinpoints the site of the lesion
The drug lessens inflammation without harming the tissue
Annotation errors skew the benchmark toward easy cases
Long reads resolve the repeats that short reads collapse
Binding lags behind expression by about two hours
The decay curve steepens after the third week
Pooling samples hides variation between donors
Signal tapers off toward the distal end
The method outpaces its closest competitor on large inputs
Cells do not recover after the second heat shock
Mutants in the pathway have lost the ability to migrate
Replicates cluster by batch rather than by condition
Peak calls were filtered with a fixed threshold
The effect is lost in older animals
Does the model generalize to unseen species?
Why do some enhancers act at long range?
Deeper sequencing uncovers hundreds of new transcripts
Gene loss underlies the change in limb shape
Receptors cluster at the leading edge of moving cells
Neighboring cells coordinate their timing through shared signals
A small subset of neurons drives the entire response
Ligand binding triggers a rapid shift in conformation
Early lesions predict the course of disease
Sparse labels limit what the classifier can learn
The tool fails on inputs longer than ten thousand bases
Data from two labs agree on the main trend
Treatment prolongs survival in the mouse model
Fixation damages the epitope in some tissues
Adding noise helps the model cope with small shifts
These scores correlate poorly with human judgment
The embryo grows fastest during the first six hours
Fewer reads map to the second chromosome than expected
Removing the factor halts division within an hour
A stricter cutoff would exclude half of the true hits
Two groups of genes switch on at different times
Cells shrink as the dose rises
Batch size matters less than learning rate
Our pipeline reports every step in a single log
Sequence conservation predicts function better than expression
Adjacent genes share regulatory elements more often than chance
""".strip().split("\n")

NOUN_PHRASES_B = """
Overview of the sequencing platforms in use
A short history of the field and its tools
Methods for aligning reads to the reference
Sample metadata and quality scores per lane
Preliminary results from the pilot run
Roadmap for the next two quarters
Frequently asked questions about the pipeline
Gene expression in the developing retina
Cost estimates for the full study
List of abbreviations used in the figures
Candidate loci identified by the screen
Schematic of the experimental workflow
Limitations of the current approach
Regulatory landscape of the zebrafish genome
Protocol for the staining and imaging steps
Summary statistics for the five cohorts
Choice of control samples for each batch
Layout of the plate and the placement of replicates
Key assumptions behind the model
Spatial patterns of accessibility across the embryo
Variation in read depth along the chromosome
A framework for comparing atlas versions
The open problems in lineage reconstruction
Acknowledgments and funding sources
""".strip().split("\n")

# Corpus C. I wrote these after the rules and the lists of title_check.py were final. I measured the check on them
# once, did not change the check afterwards, and report the result.
SENTENCES_C = """
Transposable elements seed new regulatory regions in primates
Sorting cells by size removes most of the doublets
Knockout mice develop normally but age faster
Antibiotic exposure rewires the gut community within days
The two models disagree on the timing of the switch
Heart progenitors split into two groups before day three
Fewer than half of the candidate sites replicate in the second cohort
Our classifier ranks the true binders above 90 percent of decoys
Gradient noise grows as the batch shrinks
Chromatin opens before the gene turns on
Thermal shifts reveal which ligands stabilize the protein
Cells repair the damage faster at night
Local ancestry explains part of the difference in expression
Hybrid embryos inherit the paternal pattern of marks
The signal decays with the square of the distance
Contamination inflates the count of rare variants in low depth samples
Neurons in this region respond to touch and to sound
Stronger regularization closes the gap between train and test
Mapping quality drops sharply near repeats
Lineage barcodes survive the whole length of the experiment
The pathway senses oxygen through a single residue
Nutrient sensors set the pace of growth in young tissue
Smaller models can match the larger ones when data are clean
Long term culture shifts the balance toward progenitors
A third of the peaks lie within a kilobase of a start site
Three markers separate the major clusters at every stage
Early drug exposure changes the shape of the fin
Differences in sampling explain most of the apparent trend
These variants alter splicing in at least four genes
Careful controls rule out an effect of the vector
The pattern holds in every species we examined
Two pulses of signal specify the fate of each cell
Parallel runs agree to within one percent
Fast cycling cells lose the mark more often than slow ones
The enzyme tolerates changes at most surface sites
Short term stress leaves a lasting imprint on the genome
Pretraining on unlabeled data lifts accuracy by four points
Replicate lanes disagree at low coverage
The new assay detects binding that older methods miss
Mutant cells ignore the signal from their neighbors
Blocking the receptor reverses the effect of the drug
Residue contacts predict the fold of the complex
Warm nights delay flowering in the field
Each additional round adds fewer new hits
How do cells count their divisions?
Variation among individuals exceeds variation among sites
Samples degrade quickly when stored above freezing
Feedback keeps the level of the protein within a narrow band
""".strip().split("\n")

NOUN_PHRASES_C = """
Notation and definitions used in this talk
Experimental design for the second aim
Table of reagents and their sources
Genes near the strongest peaks
Quality metrics across all lanes
Pipeline for variant filtering and annotation
Questions for the discussion
Comparison with earlier benchmarks
Strategy for sampling the rare cell types
Atlas of open chromatin in the early embryo
Time course of the response to heat
Limits of the current annotation
Proposal for a shared reference
Sources of batch variation in the screen
Study design and sample collection
Toward a complete map of regulatory elements
Collaborators and funding
Details of the training procedure
Signal processing steps before peak calling
A glossary of terms for the figures
Structure of the regulatory network around the gene
Overview of the dataset and its splits
Timeline of the project from start to launch
Preliminary data on binding affinity
""".strip().split("\n")


# Corpus E. The second reviewer wrote these titles and measured the check on them. They are made up. I read the failures
# and tuned the check on them. Corpus E is a regression set.
SENTENCES_E = """
Zebrafish fins regrow within three weeks of amputation
Pooled screens identify regulators of limb patterning
Open chromatin marks the enhancers of heart genes
The reporter lights up only in the notochord
Single cells vary widely in transcript counts
Variant calling improves when reads are realigned
Off-target edits remain rare in all clones
Most peaks lie more than ten kilobases from a promoter
Depleting the cofactor silences the whole locus
Annotation errors inflate the apparent novelty of the dataset
Cell fate decisions depend on the timing of the signal
Lineage tracing reveals a second source of muscle progenitors
Batch correction removes real biology from small datasets
Heart regeneration needs an intact epicardium
The new scaffold folds in silico with high confidence
Larger models memorize more of the training set
Neural crest cells follow two distinct paths
Gene dosage buffers the effect of the mutation
Protein binders cover the full range of affinities
Our estimates agree with the published values
Embryonic stem cells exit pluripotency in stages
Imaging data show a gradient across the tissue
Drug response splits the cohort into three groups
The assay detects fewer than ten molecules per cell
Methylation spreads from the boundary into the gene body
Transposon insertions cluster at open regions
Sample size matters more than sequencing depth here
Mice fed the diet gain less weight than controls
Training on synthetic data narrows the gap to human labels
The signal peaks at 24 hours and then decays
Differential accessibility tracks with differential expression
Replicate libraries cluster by batch before correction
Inhibitors that bind the pocket also block the channel
Expression noise is lower in essential genes
Fish lacking the receptor swim in circles
Forty percent of the loci show allele-specific effects
Cortical neurons are born in a fixed order
Time-lapse movies expose a hidden mode of migration
The pipeline runs in under an hour on one node
Peak callers disagree on weak signals
Cardiomyocytes divide only in the first week after injury
Accessibility changes before expression in the neural tube
Accuracy drops on sequences longer than 2000 residues
Growth slows when the nutrient runs out
Promoters of housekeeping genes stay open in every cell type
Binding strength varies by two orders of magnitude
The mutant embryos arrest at the gastrula stage
Progenitors turn into neurons within a day
Reads map to the genome with 95% accuracy
The effect of the drug fades after the third dose
Hox genes switch on in a fixed sequence along the axis
Many enhancers act on more than one gene
Transcription bursts last about ten minutes
Candidates ranked by the model enter the next round of testing
Noise grows with the distance from the source
Cell division rates differ between the two lineages
Signals spread through the tissue in waves
The score correlates with the measured affinity
Our benchmark covers 12 tissues and 3 species
Gene loss in the fin predates the loss in the limb
Overlap between the two methods is low for rare cell types
Embryos grow normally at lower temperatures
These loci were missed by every earlier screen
The atlas contains 1.2 million cells from 40 timepoints
Scores improve with each round of fine-tuning
The cluster splits in two at higher resolution
Binding sites sit within 200 bases of the start site
Fibroblasts switch identity after a single pulse
No pair of replicates differs by more than 5%
Open regions shrink as the embryo ages
We trained the classifier on 5000 labeled peaks
Experiments confirm six of the ten predicted targets
Variants in the enhancer are linked to heart defects
Both pathways converge on the same transcription factor
Lag times depend on the lineage
Latency falls by half with the cached index
Peaks that disappear at 48 hours mark the end of the program
Hybrid embryos develop faster than either parent
Contamination affects fewer than 2% of the reads
Each module explains a different part of the variance
""".strip().split("\n")

NOUN_PHRASES_E = """
Chromatin accessibility across zebrafish development
A catalog of candidate enhancers in the developing heart
Lineage-specific regulators of neural crest fate
Benchmark of peak callers on single-cell ATAC data
Effect sizes of knockouts across seven tissues
Quality control metrics for each sequencing batch
Comparison of three alignment strategies
A map of open regions in adult fin tissue
Time course of reporter activation after heat shock
Distribution of peak widths by cell type
Proposed experiments for the next six months
Open questions in regeneration biology
Summary statistics of the training corpus
Model architecture and training details
Cell type composition of the atlas
Timeline of the project and its milestones
Candidate binders for the target receptor
Our evidence for a conserved regulatory code
Performance on held-out lineages
Motif enrichment in lineage-specific peaks
Variance explained by each principal component
Data sources and processing steps
Results from the pilot screen
Gene expression changes in treated embryos
""".strip().split("\n")


# Corpus D. I wrote these after the rules and the lists were final, in other fields (imaging, ecology, chemistry, clinical
# work and physics), and measured the check on them once. I did not tune the check on this corpus. It is an estimate for
# present-tense titles that the author of the rules wrote. Every title of the corpora A to E is in the present tense, apart
# from a few in the past. Corpus F holds past-tense titles.
SENTENCES_D = """
Super-resolution microscopy resolves the ring of actin at the neck
Light-sheet movies capture the whole embryo every two minutes
Fluorescence fades faster in the oxidized samples
Segmentation errors cluster along the thin processes
The new dye penetrates deeper into cleared tissue
Motion artifacts blur the cortex in half of the scans
Contrast improves after the deconvolution step
Cells migrate toward the source of the signal at constant speed
Warming shifts the range of the species northward
Predators suppress the number of grazers on the reef
Seedlings survive better under the canopy of native trees
Pollinator visits decline with distance from the hedgerow
Invasive plants outcompete natives in disturbed soil
Nitrogen runoff fuels algal blooms in the estuary
Bird counts rose after the wetland was restored
Soil carbon stays stable across the dry season
The catalyst converts methane to methanol at room temperature
Hydrogen bonds stabilize the folded form of the peptide
Yields drop when the solvent contains water
The reaction proceeds through a short-lived radical
Adding a ligand shifts the equilibrium toward the complex
Crystals form within a day at four degrees
The polymer degrades slowly in acidic media
Electron-rich rings accelerate the coupling step
Patients on the new regimen recover two days sooner
Blood pressure falls within a week of the first dose
The test misses early cases in younger patients
Adverse events occur mostly in the first month
Screening reduces deaths from the disease by a fifth
Older patients respond less to the standard dose
The biomarker rises months before symptoms appear
Hospital stays shorten when nurses follow the checklist
The beam loses half of its power over ten kilometers
Noise from the amplifier dominates below one kilohertz
Spins align along the field within a microsecond
The resonance shifts with the temperature of the cavity
Heat flows from the hot plate into the sample
Energy levels split in a magnetic field
The detector counts fewer events at higher thresholds
Collisions heat the gas to ten thousand kelvin
Larger samples narrow the range of plausible effects
Both measurements agree within the stated error
The model explains most of the variance in growth
Rainfall predicts yield better than soil type
Results held up in the replication study
Sensors drift over the course of a long experiment
""".strip().split("\n")

NOUN_PHRASES_D = """
Overview of the imaging setup and its resolution
Sampling sites along the river and their characteristics
Synthesis route for the lead compound
Inclusion criteria and patient flow
Field protocol for the transect counts
Calibration curves for the detector
Summary of adverse events by treatment arm
Species list for the long-term plots
Spectra of the three reference compounds
A history of the instrument and its upgrades
Experimental conditions for each sample
Cohort characteristics at baseline
Image acquisition parameters
Sources of error in the field measurements
Reaction scope and limitations
Data availability and code
Layout of the optical table
Main outcomes and secondary outcomes
Phase diagram of the alloy near the transition
Habitat maps for the three study regions
Details of the staining protocol
Questions from the field team
Schematic of the reactor
Key parameters of the simulation
Dose escalation plan for the second trial
Remaining sources of uncertainty
Plan for the next field season
Properties of the new material
""".strip().split("\n")


# Corpus F. Past-tense titles in other fields (ecology, astronomy, materials, psychology, medicine, geology). I wrote them
# before I measured the check on them. Round 3b then took shrank, slept and ate from these titles for the irregular
# list, so the sentence rate of corpus F is tuned. The tests set a bar on the sentences only (at most 10 percent
# false alarms).
# The noun phrases have no bar: a past form counts as a verb before a preposition, so a noun phrase with a participle
# ("Genes expressed in the liver") passes, and the report gives the rate.
SENTENCES_F = """
Ice cover shrank across the Arctic during the 1990s
The comet brightened within a week of perihelion
Crop yields dropped after the late frost
Volunteers slept longer on the quiet ward
The alloy cracked under repeated loading
Measles cases rose in the unvaccinated districts
The glacier retreated from the fjord in two decades
Seabirds nested on the new island within a year
Rats learned the maze faster after the training
The reactor overheated at the end of the test
Coral bleached across the reef during the heat wave
Participants recalled fewer words in the noisy room
The sample dissolved in the acid within minutes
Dust settled over the valley after the eruption
Voters changed their minds after the debate
Salinity increased near the river mouth in summer
The star dimmed for three days in October
Children ate more vegetables at the new school
The telescope detected a faint signal from the nebula
Rainfall peaked in the second week of the survey
Anxiety scores improved after eight weeks of therapy
The crust formed under high pressure in the mantle
Forest cover grew along the southern slope
Patients waited longer on weekends than on weekdays
The mixture separated into two layers at rest
Beetles invaded the orchard through the north gate
Heat flowed from the core into the mantle over millions of years
Prices climbed in every region during the drought
Neurons fired in bursts during the deep sleep
The coating peeled off in humid air
""".strip().split("\n")

NOUN_PHRASES_F = """
Overview of the survey sites in the northern region
Equipment list for the field season
Timeline of the eruption and the evacuation
Questionnaire items and scoring rules
Map of the study area and the sampling grid
Safety rules for the laboratory
Budget summary for the second year of the project
Table of material properties at room temperature
Climate records from the three weather stations
Participant characteristics by group
Interview guide for the community meetings
Layout of the pilot plant
Summary of the orbital parameters
Soil samples from the lower terrace
Schedule of the trial visits
""".strip().split("\n")


# Corpus G. Titles with set, split or spread, in several fields. In the noun phrases the word is a noun, most often
# after another word, as in "Gene set enrichment". In the sentences it is a verb in the past or the present. I wrote
# the titles and fixed the mix (10 set, 6 split, 4 spread) before I measured the check on them. Corpus G is a
# regression set.
SENTENCES_G = """
The team set a new record in the relay
Heavy rains set the planting back by a month
The committee split over the budget for the new wing
The river splits into three channels near the coast
Rising costs split the coalition before the vote
The infection spread through the colony within a week
Cracks spread along the weld under repeated load
The rumor spreads faster than the correction
""".strip().split("\n")

NOUN_PHRASES_G = """
Gene set enrichment in the treated samples
Test set accuracy for the three models
Accuracy on the held-out test set
Data set from the field survey
Training set size and label balance
Validation set results for each fold
Reference set of curated protein structures
Candidate gene set from the pilot screen
Rule set for the triage of alerts
Feature set of the baseline classifier
Train and test split for the classifier
Results across the training split
Stock split history of the firm
Random split of patients into two arms
Temporal split of the sales records
Leaf split angles in young seedlings
Spread of the epidemic in rural districts
Geographic spread of the invasive beetle
Price spread between the two regional markets
Tumor spread to the regional lymph nodes
""".strip().split("\n")


def false_alarms(titles):
    return [title for title in titles if not title_check.is_sentence(title)]


def misses(titles):
    return [title for title in titles if title_check.is_sentence(title)]


CORPORA = ("A", "B", "C", "D", "E")
MAX_FALSE_ALARMS = 0.08  # of the sentence titles
MIN_FLAGGED = 0.70  # of the noun phrases


def corpus(name):
    return globals()["SENTENCES_" + name], globals()["NOUN_PHRASES_" + name]


class Corpora(unittest.TestCase):
    def test_every_corpus_is_large_enough_and_has_its_own_titles(self):
        seen = set()
        for name in CORPORA:
            with self.subTest(corpus=name):
                sentences, nouns = corpus(name)
                self.assertGreaterEqual(len(sentences), 40)
                self.assertGreaterEqual(len(nouns), 20)
                titles = set(sentences + nouns)
                self.assertEqual(len(titles), len(sentences) + len(nouns))
                self.assertFalse(seen & titles)
                seen |= titles

    def test_at_most_8_percent_of_the_sentence_titles_are_flagged_with_no_verb_in_every_corpus(self):
        for name in CORPORA:
            with self.subTest(corpus=name):
                sentences, _ = corpus(name)
                flagged = false_alarms(sentences)
                self.assertLessEqual(len(flagged), MAX_FALSE_ALARMS * len(sentences), flagged)

    def test_at_least_70_percent_of_the_noun_phrases_are_flagged_in_every_corpus(self):
        for name in CORPORA:
            with self.subTest(corpus=name):
                _, nouns = corpus(name)
                passed = misses(nouns)
                self.assertLessEqual(len(passed), (1 - MIN_FLAGGED) * len(nouns), passed)


MAX_FALSE_ALARMS_PAST = 0.10  # of the past-tense sentence titles of corpus F


class PastTenseCorpus(unittest.TestCase):
    """Corpus F has a bar on the sentences only. The report gives the rate of the noun phrases."""

    def test_the_corpus_is_large_enough_and_has_its_own_titles(self):
        self.assertGreaterEqual(len(SENTENCES_F), 25)
        self.assertGreaterEqual(len(NOUN_PHRASES_F), 15)
        titles = set(SENTENCES_F + NOUN_PHRASES_F)
        self.assertEqual(len(titles), len(SENTENCES_F) + len(NOUN_PHRASES_F))
        for name in CORPORA:
            sentences, nouns = corpus(name)
            self.assertFalse(titles & set(sentences + nouns), name)

    def test_at_most_10_percent_of_the_past_tense_sentence_titles_are_flagged_with_no_verb(self):
        flagged = false_alarms(SENTENCES_F)
        self.assertLessEqual(len(flagged), MAX_FALSE_ALARMS_PAST * len(SENTENCES_F), flagged)

    def test_the_noun_phrases_that_pass_are_the_ones_counted_by_hand(self):
        # Counted by hand: the lists read "sites" as the -es form of the plain verb "sit". So 14 of 15 are flagged.
        self.assertEqual(misses(NOUN_PHRASES_F), ["Overview of the survey sites in the northern region"])

    def test_a_past_form_before_a_preposition_counts_so_a_participle_passes_by_design(self):
        # "Genes expressed in the liver" is a noun phrase, and "The comet brightened within a week" is a sentence.
        # The shapes are the same. The check reads both as sentences and accepts the miss.
        self.assertTrue(title_check.is_sentence("The comet brightened within a week of perihelion"))
        self.assertTrue(title_check.is_sentence("Genes expressed in the liver"))

    def test_a_past_form_before_a_determiner_or_an_adverb_counts(self):
        self.assertTrue(title_check.is_sentence("The reactor overheated the whole room"))
        self.assertTrue(title_check.is_sentence("The bridge collapsed quickly"))


MIN_FLAGGED_G = 0.90  # of the noun phrases of corpus G
MIN_PASSED_G = 0.75  # of the sentences of corpus G


class SameFormCorpus(unittest.TestCase):
    """Corpus G: the words set, split and spread as nouns and as verbs."""

    def test_the_corpus_is_large_enough_and_has_its_own_titles(self):
        self.assertGreaterEqual(len(NOUN_PHRASES_G), 15)
        self.assertGreaterEqual(len(SENTENCES_G), 8)
        titles = set(SENTENCES_G + NOUN_PHRASES_G)
        self.assertEqual(len(titles), len(SENTENCES_G) + len(NOUN_PHRASES_G))
        for name in CORPORA + ("F",):
            sentences, nouns = corpus(name)
            self.assertFalse(titles & set(sentences + nouns), name)

    def test_every_noun_phrase_holds_set_split_or_spread(self):
        for title in NOUN_PHRASES_G:
            words = title.lower().split()
            with self.subTest(title=title):
                self.assertTrue(any(word in ("set", "split", "spread") for word in words))

    def test_at_least_90_percent_of_the_noun_phrases_are_flagged(self):
        passed = misses(NOUN_PHRASES_G)
        self.assertGreaterEqual(len(NOUN_PHRASES_G) - len(passed), MIN_FLAGGED_G * len(NOUN_PHRASES_G), passed)

    def test_at_least_75_percent_of_the_sentences_pass(self):
        flagged = false_alarms(SENTENCES_G)
        self.assertGreaterEqual(len(SENTENCES_G) - len(flagged), MIN_PASSED_G * len(SENTENCES_G), flagged)


class Docstring(unittest.TestCase):
    def test_the_module_docstring_states_the_limits_of_the_check(self):
        text = " ".join(title_check.__doc__.split())
        for phrase in ("T3 heuristic", "closed verb list", "A past form counts before a preposition",
                       "Genes expressed in the liver", "noun phrase with a participle passes",
                       "noun + intransitive verb form + preposition", "cannot be told apart",
                       "can warn wrongly or pass wrongly", "The author decides", "Recent changes in policy",
                       "Major gains in accuracy"):
            self.assertIn(phrase, text)

    def test_the_limits_name_the_past_forms_that_are_nouns_and_the_same_form_words(self):
        text = " ".join(title_check.__doc__.split())
        for phrase in ("bound, felt, left, rose, saw, shot, spoke, thought, won", "A lower bound on the error rate",
                       "Flu shot uptake", "Wild rose genome", "led (LED)", "sled, testbed, seabed", "Rocket sled tests",
                       "Gene set enrichment", "The team set a record", "The committee split over the budget",
                       "the past form of spread before a preposition without a homograph cue", "seven corpora",
                       "Corpus G", "cost 41 units", "Patient group 3 and the control group",
                       "9 or more gave a signal above 60 au"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("Data set from the field", text)
        self.assertNotIn("Tumor spread to the lymph nodes", text)


class Rules(unittest.TestCase):
    def check(self, title, expected, label=""):
        self.assertEqual(title_check.has_verb(title), expected, "{}: {}".format(label, title))

    def test_an_auxiliary_is_a_verb_and_so_is_a_modal(self):
        for title in ("Is the model stable?", "Peaks were called with a fixed cutoff", "The score can drift", "We did not see it"):
            self.check(title, True)

    def test_a_plain_verb_counts_after_a_noun_and_not_in_first_place(self):
        self.check("Cells divide twice", True)
        self.check("Divide the cells twice", False)  # an imperative is not a headline
        self.check("The abolish list", False)  # after a determiner a word is not a verb

    def test_a_plain_verb_after_to_is_an_infinitive_and_counts(self):
        self.check("One thing to remember from this talk", True)
        self.check("A tool to detect rare peaks", True)

    def test_a_plain_verb_after_a_preposition_does_not_count(self):
        self.check("Tools for detect rare peaks", False)

    def test_a_homograph_counts_before_a_determiner_a_number_or_an_adverb(self):
        self.check("Heat stress sets the pace of growth", True)
        self.check("Samples span three orders of magnitude", True)
        self.check("The tool does not map reliably", True)

    def test_a_homograph_counts_before_digits_as_it_does_before_a_number_word(self):
        # Three headlines from real runs. Each one got the warning before digits counted as a number.
        for title in ("The Batched pipeline cost 41 units per design, against 100 for the Manual pipeline.",
                      "The Batched pipeline cost 41 units per design against 100 for the Manual pipeline",
                      "The Batched pipeline cost 41 units per design."):
            with self.subTest(title=title):
                self.check(title, True)
                self.assertIsNone(title_check.title_problem(title, 6, 20))
        self.check("The run cost three units per design", True)

    def test_a_noun_phrase_with_digits_still_warns_when_its_homograph_stands_first_or_after_a_preposition(self):
        # The homograph rules read the word before a homograph first, so the digit after it changes nothing here.
        for title in ("Figure 3 of the pilot study", "Results for model 2 under load"):
            with self.subTest(title=title):
                self.check(title, False)
                self.assertIn("no verb that this check knows", title_check.title_problem(title, 6, 20))

    def test_known_limits_a_homograph_after_a_noun_and_before_digits_passes(self):
        self.check("Patient group 3 and the control group", True)

    def test_known_limits_a_past_form_after_more_does_not_count(self):
        self.check("Every design with an Osprey score of 9 or more gave a signal above 60 au.", False)

    def test_a_homograph_before_a_preposition_does_not_count(self):
        self.check("Maps of the developing heart", False)
        self.check("Cost estimates for the full study", False)
        self.check("Steps for the second run", False)

    def test_an_intransitive_homograph_in_s_after_a_noun_counts_before_a_preposition(self):
        self.check("The pipeline runs in under an hour", True)
        self.check("Methylation spreads from the boundary", True)
        self.check("Accuracy drops on long sequences", True)
        self.check("Latency falls by half", True)
        self.check("Accessibility changes before expression", True)
        self.check("The cluster splits in two", True)
        self.check("The reporter lights up in the notochord", True)

    def test_every_word_of_the_intransitive_list_counts_in_s_form(self):
        for base in title_check._INTRANSITIVE.split():
            for form in sorted(title_check._forms(base)):
                if form == base or form.endswith(("ed", "ing")):
                    continue
                with self.subTest(form=form):
                    self.check("The signal {} in the tissue".format(form), True)

    def test_an_intransitive_homograph_before_of_for_about_per_or_between_does_not_count(self):
        for title in ("Cell maps of the heart", "Sample scores for each cohort", "Group changes about the plan",
                      "Sample groups per cohort", "Cell links between the layers"):
            self.check(title, False, "a noun phrase")

    def test_a_homograph_that_is_not_on_the_list_does_not_count_before_a_preposition(self):
        self.check("Sample sizes in the study", False)
        self.check("Batch effects from the second lab", False)

    def test_the_intransitive_form_needs_a_singular_noun_before_it(self):
        self.check("Runs in the second batch", False)
        self.check("The runs in the second batch", False)
        self.check("Samples runs in the second batch", False)

    def test_an_intransitive_homograph_in_the_base_form_needs_a_plural_subject(self):
        self.check("Signals run through the tissue", True)
        self.check("The signal run through the tissue", False)
        self.check("The signal spread through the tissue", False)  # "spread" is no past form

    def test_spread_counts_by_the_homograph_rules_only(self):
        self.check("Tumor spread to the lymph nodes", False)
        self.check("Geographic spread of the invasive beetle", False)
        self.check("The infection spread through the colony", False)  # a past form before a preposition is missed
        self.check("Cracks spread along the weld", True)  # a plural noun comes before the base form
        self.check("The fire spread the smoke", True)  # a determiner follows

    def test_set_and_split_after_a_noun_are_nouns(self):
        for title in ("Gene set enrichment", "Test set accuracy", "Data set from the field", "Train and test split",
                      "Results across the training split", "Accuracy on the held-out test set"):
            with self.subTest(title=title):
                self.check(title, False)

    def test_set_and_split_count_as_verbs_through_the_homograph_rule(self):
        self.check("The team set a record", True)  # a determiner follows
        self.check("Rising costs split the coalition", True)
        self.check("The new rules set limits on the catch", True)  # a plural noun comes before the base form
        self.check("The cluster splits in two", True)  # an intransitive -s form before a preposition

    def test_enhancers_act_on_genes(self):
        self.check("Many enhancers act on more than one gene", True)

    def test_a_noun_act_is_not_a_verb(self):
        for title in ("Random acts of kindness", "Costs of the Clean Air Act", "The Clean Air Act and its costs"):
            with self.subTest(title=title):
                self.assertFalse(title_check.is_sentence(title))

    def test_a_noun_phrase_with_a_listed_intransitive_noun_passes_and_the_docstring_says_so(self):
        self.check("Recent changes in policy", True)
        self.check("Major gains in accuracy", True)

    def test_the_word_act_counts_as_a_verb_after_a_plural_subject_and_not_in_a_noun_phrase(self):
        self.check("Several kinases act in the pathway", True)
        self.check("Acts of kindness in the lab", False)

    def test_a_homograph_in_first_place_or_after_a_determiner_does_not_count(self):
        self.check("Design of the experiment", False)
        self.check("The control group in the second cohort", False)

    def test_a_homograph_after_to_or_a_preposition_does_not_count_even_before_a_determiner(self):
        self.check("Tools to map the genome", False)
        self.check("Methods for test the pipeline", False)

    def test_a_base_homograph_after_a_singular_noun_counts_before_a_determiner_or_an_adverb(self):
        self.check("A tool and a probe map the genome", True)
        self.check("A tool and a probe map reliably", True)

    def test_a_base_homograph_after_a_plural_noun_counts(self):
        self.check("Receptors cluster by lineage", True)
        self.check("Reads map to the second chromosome", True)
        self.check("The cluster map by lineage", False)  # a singular noun before it

    def test_a_homograph_in_s_after_a_singular_noun_with_an_object_counts(self):
        self.check("The score tracks expert ratings", True)
        self.check("Cell counts per cluster", False)
        self.check("Sample sizes for each cohort", False)
        self.check("Training data and test splits", False)  # a coordinator follows or the title ends

    def test_a_past_form_counts_in_a_verb_position(self):
        self.check("Cells stained with the new dye glowed brighter", True)
        self.check("Mice lost weight", True)

    def test_a_past_form_after_a_determiner_a_preposition_or_an_adverb_does_not_count(self):
        self.check("The designed binders", False)
        self.check("Examples of failed designs", False)
        self.check("Frequently asked questions about the pipeline", False)

    def test_a_past_form_counts_before_a_preposition_before_a_coordinator_and_at_the_end(self):
        self.check("Latency fell by half", True)
        self.check("Expression declined after day 5", True)
        self.check("Expression rose and fell", True)
        self.check("Counts rose but not scores", True)  # no other verb follows the coordinator
        self.check("Expression declined", True)
        self.check("Benchmark datasets used in the comparison", True)  # a noun phrase with a participle passes
        self.check("Genes expressed in the liver", True)

    def test_every_irregular_past_form_of_the_list_counts(self):
        words = ("fell rose grew ran began led drew held kept left lost made met put sat saw sent shed shot shut "
                 "stood took told won wrote shrank slept ate").split()  # set, split and spread are no past forms
        for word in words:
            with self.subTest(word=word):
                self.check("Latency {} by half".format(word), True)
                self.check("Latency {}".format(word), True)

    def test_an_irregular_past_form_after_a_determiner_a_preposition_or_an_adverb_does_not_count(self):
        for title in ("A set of samples", "The split between sites", "Examples of lost data", "A shed in the field",
                      "Often left by half", "Left ventricle size"):
            with self.subTest(title=title):
                self.check(title, False)

    def test_a_regular_ed_word_of_four_letters_or_more_counts_wherever_a_past_form_can_stand(self):
        self.check("Crowds fled by night", True)
        self.check("Cells zorbled in the dark", True)
        self.check("Cells zorbled", True)

    def test_a_word_of_three_letters_in_ed_is_not_a_past_form(self):
        self.check("Mice red by the door", False)
        self.check("Mice bed by the door", False)

    def test_an_ed_noun_or_adjective_that_is_no_verb_does_not_count(self):
        for word in ("sacred", "naked", "wicked", "indeed", "weed", "deed", "reed", "heed", "creed", "greed", "bleed",
                     "proceed", "kindred", "hatred"):
            with self.subTest(word=word):
                self.check("Cells {} in the dark".format(word), False)
                self.check("Cells {}".format(word), False)

    def test_a_past_form_in_first_place_does_not_count(self):
        self.check("Expressed genes in the liver", False)
        self.check("Zorbled cells in the dark", False)

    def test_an_ing_word_before_a_determiner_a_preposition_or_an_adverb_counts(self):
        self.check("Cells growing in the dark", True)
        self.check("Mice growing rapidly", True)
        self.check("Binders improving the fit", True)

    def test_an_ing_word_in_first_place_or_before_a_noun_does_not_count(self):
        self.check("Variant calling pipeline", False)
        self.check("Quality control metrics for the sequencing run", False)
        self.check("Data sources and processing steps", False)
        self.check("Sequencing the genome", False)

    def test_an_ing_word_after_a_preposition_does_not_count(self):
        self.check("Methods for aligning reads to the reference", False)
        self.check("Tools for sequencing the genome", False)

    def test_known_limits_the_check_passes_these_noun_phrases(self):
        # An unknown plural noun after a singular word and before a noun reads as a verb and its object.
        self.check("A framework for comparing atlas versions", True)
        # An intransitive homograph in -s form reads as a verb before "in", and so does a noun that is on the list.
        self.check("Gene expression changes in treated embryos", True)
        # A homograph that follows a prepositional phrase has no plural noun right before it.
        self.check("Only 11 of 52 test items in our review rest on a study", False)

    def test_known_limits_a_past_form_that_is_also_a_noun_passes_after_a_word(self):
        # The Limits paragraph of the module docstring names these words. The check accepts the misses.
        for title in ("A lower bound on the error rate", "Upper bound on the sample size",
                      "Flu shot uptake in older adults", "Wild rose genome", "Wool felt samples from the mill",
                      "Upper left corner of the plate", "Band saw safety rules", "Wheel spoke tension",
                      "Recent thought on the origin of life", "Korean won exchange rates",
                      "Blue LED arrays for the growth chamber", "Rocket sled tests", "A robotic testbed for field trials",
                      "Deep seabed mining"):
            with self.subTest(title=title):
                self.check(title, True)

    def test_committee_split_over_the_budget_gets_the_warning_because_split_is_no_past_form(self):
        self.check("The committee split over the budget", False)
        self.check("The committee split the budget", True)

    def test_an_unknown_word_in_s_before_a_determiner_after_a_singular_noun_counts(self):
        self.check("The tool frobnicates the data", True)
        self.check("Datasets blorfs in the comparison", False)  # an unknown word in -s before a preposition is a noun
        self.check("The tool frobnicates sacred data", True)  # an -ed word that is no past form does not hide the verb
        self.check("Sample ids the new table", False)  # an unknown word of 3 letters in -s is a plural noun

    def test_an_unknown_base_word_after_a_plural_noun_before_a_determiner_counts(self):
        self.check("Doses zorble a stronger response", True)
        self.check("Doses zorble stronger responses", False)
        self.check("Differences between the old and the new protocol", False)

    def test_an_unknown_ed_or_ing_word_counts_in_a_verb_position(self):
        self.check("The assay zorbled the signal", True)
        self.check("The assay zorbling the signal", True)
        self.check("Cells zorbling in the dark", True)
        self.check("Cells zorbled in the dark", True)
        self.check("The zorbled cells", False)
        self.check("The zorbling cells", False)

    def test_an_unknown_word_in_s_that_ends_in_ics_is_not_a_plural_noun(self):
        self.check("Population genetics tools for the lab", False)
        self.check("The tool statics the data", False)  # a word in -ics is read as a noun, never as a verb form

    def test_a_plural_noun_before_a_past_form_is_not_read_as_a_verb_but_the_past_form_counts(self):
        self.check("Benchmark datasets shown in the figure", True)
        self.check("Benchmark datasets used in the figure", True)

    def test_the_endings_izes_ises_and_ifies_count(self):
        self.check("The assay frobnizes across lanes", True)
        self.check("The assay frobnises across lanes", True)
        self.check("The assay frobnifies across lanes", True)
        self.check("The assay normalizes across lanes", True)
        self.check("The new assay normalizes counts across lanes", True)
        self.check("Pruning simplifies the graph", True)

    def test_a_word_with_a_digit_or_a_non_ascii_letter_is_read(self):
        self.check("12 of 15 targets bind well", True)
        self.check("Cells at 5 \u00b5M grow slowly", True)
        self.check("\u03b1 helices stabilize the fold", True)

    def test_an_empty_title_has_no_verb(self):
        self.check("", False)
        self.check("   ", False)

    def test_one_word_is_never_a_sentence(self):
        self.assertFalse(title_check.is_sentence("Is"))
        self.assertFalse(title_check.is_sentence("May"))

    def test_a_sentence_has_two_words_and_a_verb(self):
        self.assertFalse(title_check.is_sentence("Results"))
        self.assertFalse(title_check.is_sentence("Divide"))
        self.assertTrue(title_check.is_sentence("Cells divide"))


class TitleProblem(unittest.TestCase):
    def test_a_good_title_has_no_problem(self):
        self.assertIsNone(title_check.title_problem("Binder design succeeds for 12 of 15 targets", 6, 20))

    def test_a_topic_label_is_named_first(self):
        self.assertIn("topic label", title_check.title_problem("Results", 6, 20))
        self.assertIn("topic label", title_check.title_problem("Results", 1, 20))

    def test_the_word_count_comes_next(self):
        self.assertEqual(title_check.title_problem("Binders fold in nine designs", 6, 20),
                         "the title has 5 words; use 6 to 20 words")
        self.assertIn("21 words", title_check.title_problem("Binders fold " + "again " * 18 + "now", 6, 20))

    def test_the_verb_check_comes_last(self):
        message = title_check.title_problem("Overview of the methods and the background material", 6, 20)
        self.assertEqual(message, "the title has no verb that this check knows. Use a plain verb, "
                                  "or ignore this warning if the title is a sentence.")

    def test_the_boundaries_of_the_word_count(self):
        self.assertIsNone(title_check.title_problem("Binders fold in nine of twelve", 6, 6))
        self.assertIsNotNone(title_check.title_problem("Binders fold in nine of twelve", 7, 20))
        self.assertIsNotNone(title_check.title_problem("Binders fold in nine of twelve", 1, 5))


class TopicLabel(unittest.TestCase):
    def test_a_single_label_matches_with_any_case_and_end_mark(self):
        for title in ("Results", "RESULTS.", "  methods ", "Next steps!", "Future work", "Model performance"):
            with self.subTest(title=title):
                self.assertTrue(title_check.is_topic_label(title))

    def test_a_sentence_is_not_a_label(self):
        self.assertFalse(title_check.is_topic_label("Results improve after the second round"))
