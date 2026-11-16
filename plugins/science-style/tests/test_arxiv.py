"""Tests for lab/lab_arxiv.py. All text in this file is made up."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_arxiv as la  # noqa: E402
import lab_jats as lj  # noqa: E402
import lab_text as lt  # noqa: E402

META = {"work_id": "W4", "person": "ben", "route": "arxiv-html", "group": "senior", "text_version": "arxiv"}

DOC = """<!DOCTYPE html><html lang="en"><head><title>Spore nets</title><meta charset="utf-8"></head><body>
<div class="ltx_page_main"><article class="ltx_document ltx_authors_1line">
<h1 class="ltx_title ltx_title_document">Spore nets</h1>
<div class="ltx_authors"><span class="ltx_creator ltx_role_author"><span class="ltx_personname">Ben Rowan</span></span></div>
<div class="ltx_abstract"><h6 class="ltx_title ltx_title_abstract">Abstract</h6>
<p class="ltx_p" id="id1.id1">We train a net on spores.</p></div>
<div id="p1" class="ltx_para ltx_noindent"><p class="ltx_p">marginparsep has been altered.
<br class="ltx_break">topmargin has been altered.</p></div>
<section class="ltx_section" id="S1"><h2 class="ltx_title ltx_title_section"><span class="ltx_tag ltx_tag_section">1 </span>Introduction</h2>
<div class="ltx_para" id="S1.p1"><p class="ltx_p">Spores vary <cite class="ltx_cite ltx_citemacro_citep">(<a class="ltx_ref" href="#bib.bib1">Ash et al.</a>, <a class="ltx_ref" href="#bib.bib1">2001</a>)</cite>.</p></div>
<div class="ltx_para" id="S1.p2"><p class="ltx_p">Here we fit <math class="ltx_Math" alttext="y=x"><semantics><mi>y</mi></semantics></math> to counts<span class="ltx_note ltx_role_footnote"><sup class="ltx_note_mark">1</sup><span class="ltx_note_outer"><span class="ltx_note_content">A footnote.</span></span></span>.</p></div>
</section>
<section class="ltx_section" id="S2"><h2 class="ltx_title ltx_title_section"><span class="ltx_tag ltx_tag_section">2 </span>Experiments</h2>
<div class="ltx_para"><p class="ltx_p">The net found 9 spore types.</p></div>
<section class="ltx_subsection" id="S2.SS1"><h3 class="ltx_title ltx_title_subsection"><span class="ltx_tag ltx_tag_subsection">2.1 </span>Training</h3>
<div class="ltx_para"><p class="ltx_p">We trained for 3 days.</p>
<table class="ltx_equation ltx_eqn_table"><tr><td><math alttext="L"><mi>L</mi></math></td></tr></table>
<p class="ltx_p">Loss fell.</p></div>
<figure class="ltx_figure" id="S2.F1"><img src="x.png"/><figcaption class="ltx_caption"><span class="ltx_tag ltx_tag_figure">Figure 1: </span>Loss over time.</figcaption></figure>
</section></section>
<section class="ltx_section" id="S3"><h2 class="ltx_title ltx_title_section"><span class="ltx_tag ltx_tag_section">3 </span>Conclusion</h2>
<div class="ltx_para"><p class="ltx_p">Nets sort spores &amp; seeds.</p></div></section>
<div class="ltx_acknowledgements"><h6>Acknowledgements</h6><p class="ltx_p">We thank the moss.</p></div>
<section class="ltx_bibliography" id="bib"><h2 class="ltx_title ltx_title_bibliography">References</h2><ul><li><p class="ltx_p">Ash 2001.</p></li></ul></section>
<section class="ltx_appendix" id="A1"><h2 class="ltx_title ltx_title_appendix">Appendix A Extra</h2><div class="ltx_para"><p class="ltx_p">Extra text.</p></div></section>
</article></div></body></html>"""


class ArxivTests(unittest.TestCase):
    def setUp(self):
        self.paper = la.read_arxiv_html(DOC.encode("utf-8"), META)

    def test_the_abstract(self):
        self.assertEqual(self.paper["abstract"], ["We train a net on spores."])

    def test_sections_headings_and_kinds(self):
        self.assertEqual([(s["heading"], s["kind"]) for s in self.paper["sections"]],
                         [("Introduction", "intro"), ("Experiments", "results"), ("Conclusion", "discussion")])

    def test_citations_formulas_and_footnotes(self):
        self.assertEqual(self.paper["sections"][0]["paragraphs"],
                         ["Spores vary [CIT].", "Here we fit [EQ] to counts."])

    def test_subsections_and_equation_tables(self):
        experiments = self.paper["sections"][1]
        self.assertEqual(experiments["paragraphs"], ["The net found 9 spore types."])
        self.assertEqual(experiments["subsections"], [{"heading": "Training",
                                                       "paragraphs": ["We trained for 3 days. [EQ] Loss fell."]}])

    def test_legends(self):
        self.assertEqual(self.paper["legends"], ["Loss over time."])

    def test_nested_figure_panels_give_each_legend_once(self):
        page = ('<html><body><article class="ltx_document"><section class="ltx_section">'
                '<h2 class="ltx_title">Results</h2><div class="ltx_para"><p class="ltx_p">Two panels.</p></div>'
                '<figure class="ltx_figure" id="F1">'
                '<figure class="ltx_figure ltx_figure_panel"><img src="a.png"/><figcaption class="ltx_caption">'
                '<span class="ltx_tag ltx_tag_figure">(a) </span>Left panel.</figcaption></figure>'
                '<figure class="ltx_figure ltx_figure_panel"><img src="b.png"/><figcaption class="ltx_caption">'
                'Right panel.</figcaption></figure>'
                '<figcaption class="ltx_caption"><span class="ltx_tag ltx_tag_figure">Figure 1: </span>'
                'Both panels.</figcaption></figure></section></article></body></html>')
        paper = la.read_arxiv_html(page, META)
        self.assertEqual(paper["legends"], ["Left panel.", "Right panel.", "Both panels."])

    def test_references_appendix_and_acknowledgements_are_dropped(self):
        text = lt.canonical_text(self.paper)
        for gone in ("Ash 2001.", "Extra text.", "We thank the moss.", "Ben Rowan", "marginparsep"):
            self.assertNotIn(gone, text)
        self.assertIn("Nets sort spores & seeds.", text)

    def test_a_display_equation_stays_inside_its_paragraph(self):
        page = ('<html><body><article class="ltx_document"><div class="ltx_para"><p class="ltx_p">We fit</p>'
                '<table class="ltx_equation ltx_eqn_table"><tr><td><math alttext="y"><mi>y</mi></math></td></tr>'
                '</table><p class="ltx_p">, where y counts spores.</p>'
                '<div class="ltx_equationgroup"><math alttext="z"><mi>z</mi></math></div>'
                '<p class="ltx_p">Then z follows.</p></div>'
                '<p class="ltx_p">A bare paragraph.</p></article></body></html>')
        paper = la.read_arxiv_html(page, META)
        self.assertEqual(paper["sections"][0]["paragraphs"],
                         ["We fit [EQ], where y counts spores. [EQ] Then z follows.", "A bare paragraph."])

    def test_a_paragraph_of_only_equations_is_dropped(self):
        page = ('<html><body><article class="ltx_document"><div class="ltx_para">'
                '<table class="ltx_equation"><tr><td><math alttext="y"><mi>y</mi></math></td></tr></table></div>'
                '<div class="ltx_para"><p class="ltx_p">Nets sort spores.</p></div></article></body></html>')
        paper = la.read_arxiv_html(page, META)
        self.assertEqual(paper["sections"][0]["paragraphs"], ["Nets sort spores."])

    def test_a_list_inside_a_paragraph_keeps_its_items(self):
        page = ('<html><body><article class="ltx_document"><div class="ltx_para"><p class="ltx_p">Two kinds:</p>'
                '<ul class="ltx_itemize"><li class="ltx_item"><div class="ltx_para"><p class="ltx_p">Moss.</p></div>'
                '</li><li class="ltx_item"><div class="ltx_para"><p class="ltx_p">Fern.</p></div></li></ul></div>'
                '</article></body></html>')
        paper = la.read_arxiv_html(page, META)
        self.assertEqual(paper["sections"][0]["paragraphs"], ["Two kinds:", "Moss.", "Fern."])

    def test_metadata_type_and_hash(self):
        self.assertEqual((self.paper["work_id"], self.paper["text_version"]), ("W4", "arxiv"))
        self.assertEqual(self.paper["article_type"], "arxiv")
        self.assertFalse(self.paper["jats_manuscript"])
        self.assertEqual(len(self.paper["sha256"]), 64)

    def test_related_work_after_the_results_becomes_other(self):
        def section(number, title):
            return ('<section class="ltx_section"><h2 class="ltx_title ltx_title_section">'
                    '<span class="ltx_tag ltx_tag_section">{} </span>{}</h2>'
                    '<div class="ltx_para"><p class="ltx_p">Text of {}.</p></div></section>'.format(number, title, title))
        page = ('<html><body><article class="ltx_document">' + section(1, "Introduction") + section(2, "Experiments")
                + section(3, "Related Work") + section(4, "Conclusion") + "</article></body></html>")
        paper = la.read_arxiv_html(page, META)
        self.assertEqual([(s["heading"], s["kind"]) for s in paper["sections"]],
                         [("Introduction", "intro"), ("Experiments", "results"), ("Related Work", "other"),
                          ("Conclusion", "discussion")])
        early = ('<html><body><article class="ltx_document">' + section(1, "Introduction")
                 + section(2, "Related Work") + section(3, "Experiments") + "</article></body></html>")
        self.assertEqual([s["kind"] for s in la.read_arxiv_html(early, META)["sections"]],
                         ["intro", "intro", "results"])

    def test_an_essay_keeps_other_sections(self):
        paper = la.read_arxiv_html(DOC, dict(META, group="essay"))
        self.assertEqual(paper["sections"][1]["kind"], "other")

    def test_a_page_without_sections_keeps_its_text_as_the_body(self):
        page = ('<html><body><article class="ltx_document"><div class="ltx_para"><p class="ltx_p">Nets sort spores.'
                '</p></div><div class="ltx_para"><p class="ltx_p">They learn fast.</p></div></article></body></html>')
        paper = la.read_arxiv_html(page, META)
        self.assertEqual([(s["kind"], s["paragraphs"]) for s in paper["sections"]],
                         [("body", ["Nets sort spores.", "They learn fast."])])

    def test_a_page_without_a_latexml_document_is_refused(self):
        with self.assertRaises(lj.ReaderError):
            la.read_arxiv_html(b"<html><body><p>Hello.</p></body></html>", META)


if __name__ == "__main__":
    unittest.main()
