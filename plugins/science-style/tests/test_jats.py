"""Tests for lab/lab_jats.py. All text in this file is made up."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_jats as lj  # noqa: E402

META = {"work_id": "W1", "person": "ada", "route": "ncbi-pmc", "group": "senior"}

MANUSCRIPT = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE pmc-articleset PUBLIC "-//NLM//DTD ARTICLE SET 2.0//EN" "https://dtd.nlm.nih.gov/ncbi/pmc/articleset/nlm-articleset-2.0.dtd">
<pmc-articleset><article xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:mml="http://www.w3.org/1998/Math/MathML" article-type="research-article">
<front><article-meta>
<article-id pub-id-type="pmcid">PMC0000001</article-id>
<article-id pub-id-type="manuscript">NIHMS000001</article-id>
<title-group><article-title>Fern spores swell</article-title></title-group>
<abstract><p>Fern spores swell in water.</p><p>We show how they split.</p></abstract>
<abstract abstract-type="graphical"><p>Graphical text.</p></abstract>
</article-meta></front>
<body>
<sec><title>Introduction</title>
<p>Spores need water to grow (<xref ref-type="bibr" rid="r1">Ash et al., 2001</xref>; <xref ref-type="bibr" rid="r2">Birch, 2003</xref>).</p>
<p>Here we ask how spores split.<sup><xref ref-type="bibr" rid="r3">3</xref>,<xref ref-type="bibr" rid="r4">4</xref></sup></p>
</sec>
<sec><title>Results</title>
<sec><title>Spores swell in five minutes</title>
<p>Spores swelled by <inline-formula><mml:math><mml:mn>2</mml:mn></mml:math></inline-formula> fold (<xref ref-type="fig" rid="f1">Figure 1A</xref>).</p>
<fig id="f1"><label>Figure 1</label><caption><title>Spores in water.</title><p>Each dot is one spore.</p></caption></fig>
</sec>
<sec><title>Coats split along a seam</title>
<p>The coat split along one seam.</p>
<list><list-item><p>First item of a list.</p></list-item><list-item><p>Second item.</p></list-item></list>
<sec><title>A deeper part</title><p>Deep text.</p><sec><title>Deepest</title><p>Deepest text.</p></sec></sec>
</sec>
</sec>
<sec><title>Discussion</title><p>Water drives the split.</p></sec>
<sec sec-type="methods"><title>STAR Methods</title><p>We soaked 40 spores.</p><sec><title>Lead contact</title><p>Write to the lab.</p></sec></sec>
<sec><title>Data availability</title><p>Data are in a repository.</p></sec>
</body>
<back><ref-list><ref id="r1"><mixed-citation>Ash 2001</mixed-citation></ref></ref-list></back>
<floats-group><table-wrap id="t1"><caption><p>Table of spore sizes.</p></caption></table-wrap></floats-group>
</article></pmc-articleset>"""

NATURE = b"""<article article-type="research-article"><front><article-meta><abstract><p>Moss dries and recovers.</p></abstract></article-meta></front>
<body><p>Moss lives on rocks.</p><p>Here we follow one mat.</p>
<sec><title>Mats shrink within hours</title><p>Mats shrank by half.</p></sec>
<sec><title>Rain restores the mats</title><p>Rain restored them.</p></sec>
<sec><title>Discussion</title><p>Moss tolerates drying.</p></sec>
<sec sec-type="methods"><title>Online content</title><p>We weighed 12 mats.</p></sec>
</body></article>"""

SCIENCE = b"""<article article-type="research-article"><body><p>Moss dries.</p><p>It recovers in rain.</p></body></article>"""

ESSAY = b"""<article article-type="article-commentary"><body><p>Moss is a good model.</p>
<sec><title>Why moss matters</title><p>It dries and lives.</p></sec>
<sec><title>What to measure next</title><p>Measure water.</p></sec></body></article>"""


def kinds(paper):
    return [s["kind"] for s in paper["sections"]]


class HeadingTests(unittest.TestCase):
    def test_heading_kinds(self):
        cases = {"Introduction": "intro", "Background": "intro", "Results and Discussion": "results",
                 "Materials and Methods": "methods", "Experimental Procedures": "methods",
                 "STAR★Methods": "methods", "Methods summary": "methods", "2. Results": "results",
                 "Conclusions": "discussion", "Acknowledgments": "drop", "Supplementary Materials": "drop",
                 "Data and code availability": "drop", "Author contributions": "drop",
                 "Related Work": "intro", "Why moss matters": "other", "A method to image moss": "other",
                 "A reference atlas of moss": "other", "Contributions of each gene": "other"}
        for heading, kind in cases.items():
            self.assertEqual(lj.heading_kind(heading), kind, heading)

    def test_heading_kinds_for_reference_and_methods_variants(self):
        cases = {"Reference genome": "other", "Reference genome and annotation": "other",
                 "Reference-free evaluation": "other", "References": "drop", "Reference": "drop",
                 "Reference list": "drop", "Bibliography": "drop", "Literature Cited": "drop",
                 "Materials & Methods": "methods", "Material & Methods": "methods",
                 "Patients and Methods": "methods", "Subjects and Methods": "methods",
                 "2. Subjects and methods": "methods"}
        for heading, kind in cases.items():
            self.assertEqual(lj.heading_kind(heading), kind, heading)

    def test_heading_kinds_drop_ml_back_matter(self):
        cases = {"Checklist": "drop", "NeurIPS Paper Checklist": "drop", "Reproducibility Statement": "drop",
                 "Ethics Statement": "drop", "Broader Impact": "drop", "Impact Statement": "drop",
                 "Limitations": "other", "Checking the model": "other"}
        for heading, kind in cases.items():
            self.assertEqual(lj.heading_kind(heading), kind, heading)

    def test_a_methods_section_with_an_ampersand_is_not_inferred_as_results(self):
        paper = lj.read_jats(b"<article><body><sec><title>Introduction</title><p>Moss grows.</p></sec>"
                             b"<sec><title>Moss dries fast</title><p>Moss dried.</p></sec>"
                             b"<sec><title>Materials &amp; Methods</title><p>We dried 9 mats.</p></sec>"
                             b"</body></article>", META)
        self.assertEqual(kinds(paper), ["intro", "results", "methods"])

    def test_a_reference_genome_subsection_is_kept_and_a_reference_list_is_dropped(self):
        paper = lj.read_jats(b"<article><body><sec><title>Methods</title>"
                             b"<sec><title>Reference genome and annotation</title><p>We used build 9.</p></sec>"
                             b"<sec><title>References</title><p>Ash 2001.</p></sec></sec>"
                             b"<sec><title>Reference</title><p>Birch 2003.</p></sec></body></article>", META)
        self.assertEqual([s["heading"] for s in paper["sections"][0]["subsections"]],
                         ["Reference genome and annotation"])
        self.assertEqual(kinds(paper), ["methods"])


class ManuscriptTests(unittest.TestCase):
    def setUp(self):
        self.paper = lj.read_jats(MANUSCRIPT, META)

    def test_the_abstract_without_a_type(self):
        self.assertEqual(self.paper["abstract"], ["Fern spores swell in water.", "We show how they split."])

    def test_sections_kinds_and_dropped_sections(self):
        self.assertEqual(kinds(self.paper), ["intro", "results", "discussion", "methods"])
        self.assertNotIn("Data are in a repository.", str(self.paper["sections"]))

    def test_citation_runs_become_one_mark(self):
        self.assertEqual(self.paper["sections"][0]["paragraphs"],
                         ["Spores need water to grow [CIT].", "Here we ask how spores split.[CIT]"])

    def test_formulas_and_figure_references(self):
        sub = self.paper["sections"][1]["subsections"][0]
        self.assertEqual(sub["heading"], "Spores swell in five minutes")
        self.assertEqual(sub["paragraphs"], ["Spores swelled by [EQ] fold (Figure 1A)."])

    def test_lists_and_deep_sections_flatten_into_the_subsection(self):
        sub = self.paper["sections"][1]["subsections"][1]
        self.assertEqual(sub["paragraphs"], ["The coat split along one seam.", "First item of a list.",
                                             "Second item.", "Deep text.", "Deepest text."])
        self.assertEqual(self.paper["sections"][1]["paragraphs"], [])

    def test_legends_from_the_body_and_the_floats(self):
        self.assertEqual(self.paper["legends"], ["Spores in water. Each dot is one spore.", "Table of spore sizes."])

    def test_manuscript_flag_type_counts_and_hash(self):
        self.assertTrue(self.paper["jats_manuscript"])
        self.assertEqual(self.paper["article_type"], "research-article")
        self.assertIn("methods", self.paper["word_counts"])
        self.assertEqual(len(self.paper["sha256"]), 64)

    def test_metadata_passes_through(self):
        self.assertEqual((self.paper["work_id"], self.paper["route"], self.paper["person"]),
                         ("W1", "ncbi-pmc", "ada"))

    def test_the_article_doi_is_read_in_lower_case(self):
        self.assertIsNone(self.paper["article_doi"])
        doc = (b'<article><front><article-meta><article-id pub-id-type="pmcid">PMC0000002</article-id>'
               b'<article-id pub-id-type="doi">10.1101/2021.02.03.000222</article-id></article-meta></front>'
               b'<body><p>Moss dries.</p></body></article>')
        self.assertEqual(lj.read_jats(doc, META)["article_doi"], "10.1101/2021.02.03.000222")
        upper = doc.replace(b"10.1101/2021.02.03.000222", b"https://doi.org/10.1000/FERN.9")
        self.assertEqual(lj.read_jats(upper, META)["article_doi"], "10.1000/fern.9")


class ShapeTests(unittest.TestCase):
    def test_unheaded_lead_is_intro_and_descriptive_sections_become_results(self):
        paper = lj.read_jats(NATURE, META)
        self.assertEqual(kinds(paper), ["intro", "results", "results", "discussion", "methods"])
        self.assertEqual(paper["sections"][0]["paragraphs"], ["Moss lives on rocks.", "Here we follow one mat."])
        self.assertFalse(paper["jats_manuscript"])

    def test_a_paper_without_headings_is_one_body_section(self):
        paper = lj.read_jats(SCIENCE, META)
        self.assertEqual(kinds(paper), ["body"])
        self.assertEqual(paper["sections"][0]["paragraphs"], ["Moss dries.", "It recovers in rain."])

    def test_an_essay_keeps_other_sections(self):
        self.assertEqual(kinds(lj.read_jats(ESSAY, META)), ["intro", "other", "other"])
        self.assertEqual(kinds(lj.read_jats(NATURE, dict(META, group="essay")))[1], "other")

    def test_no_body_gives_no_sections(self):
        paper = lj.read_jats(b"<article><front><article-meta><abstract><p>Only this.</p></abstract>"
                             b"</article-meta></front></article>", META)
        self.assertEqual(paper["sections"], [])
        self.assertEqual(paper["abstract"], ["Only this."])

    def test_an_encoding_declaration_and_accents(self):
        paper = lj.read_jats(b'<?xml version="1.0" encoding="UTF-8"?><article><body><p>Caf\xc3\xa9 spores swell.'
                             b'</p></body></article>', META)
        self.assertEqual(paper["sections"][0]["paragraphs"], ["Café spores swell."])


class RefusalTests(unittest.TestCase):
    def test_an_entity_declaration_is_refused(self):
        doc = b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "boom">]><article><body><p>&x;</p></body></article>'
        with self.assertRaises(lj.ReaderError) as ctx:
            lj.read_jats(doc, META)
        self.assertIn("entity", str(ctx.exception))

    def test_malformed_xml_is_refused(self):
        with self.assertRaises(lj.ReaderError):
            lj.read_jats(b"<article><body><p>open</body></article>", META)

    def test_a_document_without_an_article_is_refused(self):
        with self.assertRaises(lj.ReaderError):
            lj.read_jats(b"<pmc-articleset><error>none</error></pmc-articleset>", META)


if __name__ == "__main__":
    unittest.main()
