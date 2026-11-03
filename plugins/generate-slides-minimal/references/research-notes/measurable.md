# Measurable slide design rules for a .pptx linter

Environment: python-pptx 0.6.23, Python 3.6.8. Tiers: T1 = standard or study I opened. T2 = a named source states the number; none of the T2 sources that I opened cites evidence for it. T3 = folklore, derived by me, or no source. Source keys map to URLs in section 5. "Resolve size" means run size, then shape list style, layout, master, presentation default (section 3).

## 1. Lint rules

|#|Rule|Threshold|Script measure|Tier, source|False-positive risk|
|-|-|-|-|-|-|
|1|Body text size|error <18 pt; warn <24 pt|Resolve size per run; apply a:normAutofit@fontScale from XML|T2 HARV 18-24, MSA 18, UEF 24; KAW 30 (secondary copy)|Footnotes, source lines, table cells|
|2|Title size|>=28 pt|Resolve size of title runs|T2 HARV|Divider slides|
|3|Fonts per slide|<=2 families, <=3 sizes (CDC: 2 and 2)|Sets of resolved names and sizes; None means theme font|T2 CDC|Code font|
|4|Text contrast|warn <4.5:1; error <3:1; 3:1 only for >=18 pt or >=14 pt bold|WCAG formula on font.color.rgb versus shape fill or slide background; read theme colours from theme XML|T1 WCAG-CM, WCAG-DEF; AAA 7:1 and 4.5:1 in WCAG-E|Text on photos or gradients; inherited colours|
|5|Graphic contrast|>=3:1 for chart marks and icons|Series fill RGB versus plot or slide background|T1 WCAG-NT|Marks with direct labels are exempt|
|6|Red and green|No red-hue and green-hue pair unless luminance ratio >=3:1|HSL hue bands on series and shape fills|T2 JFLY; T1 WCAG-UC (non-colour cue)|Brand palettes|
|7|Words per slide|warn >40|Count words in frames and tables; skip notes|T2 UEF; GA13 observed 41.5 versus 21.2, no threshold|Appendix slides|
|8|Bullets per list|<=4|Count same-level paragraphs per shape|T2 HARV|Agenda slides|
|9|Elements per slide|<=6|Count shapes except title and footer|T2 NAEGLE (cites a TEDx talk)|Grouped icons|
|10|Lines per paragraph|<=2|Estimate: characters x 0.5 em / box width; exact count needs a render|T2 HARV|Estimate error|
|11|Title length|<=2 lines|Same estimate on the title|T2 GA13 (Alley criterion, bundled with five other principles)|Same|
|12|Slide count|<= talk minutes|len(prs.slides) minus hidden; talk length is an input|T2 HARV, NAEGLE 1 per minute; KAW 10 per 20 min; UEF 8-10 per 10-12 min|Backup slides|
|13|Slide title|non-empty and unique|shapes.title text, compared across the deck|T2 MSA|Title slide|
|14|Alt text|descr present, not equal to the file name|XML p:cNvPr@descr|T2 MSA|Decorative images|
|15|Image resolution|effective >=144 ppi (1080p); >=288 ppi (4K)|image.size x (1 - crops) / width in inches|T3 arithmetic: 1920 px over 13.333 in; MSF says 150 ppi for file size|Logos, small photos|
|16|Aspect ratio|16:9, 13.333 x 7.5 in, +-0.01|slide_width / slide_height|T2 MSS default, UEF|Venue wants 4:3; python-pptx default is 4:3|
|17|Inside slide|0 EMU outside|left, top, right, bottom versus slide size; transform group children|T3 geometry, no source needed|Bleed backgrounds|
|18|Margin|warn <0.5 in|Same boxes|T3 my value; broadcast title-safe 90% UNVERIFIED|Full-bleed images|
|19|Left-edge alignment|flag offsets <0.05 in but not equal|Cluster shape.left|T3|Intended layouts|
|20|Chart text|>= rule 1 floor|chart.font, tick_labels.font, legend.font; None means inherited|T2 NAEGLE (qualitative); number from rule 1|Chart default size unverified|
|21|Justified text|none|paragraph.alignment == JUSTIFY|T1 WCAG-VP (AAA); MSA|Rare|

Count by tier: T1 3, T2 14, T3 4.

## 2. Needs judgment, not a script

- One idea per slide and the glance test (Duarte: understood in 3 s or less, T2 DUARTE). The page gives no score.
- Colour as the only code (WCAG-UC). A script finds series without markers or labels. A reader decides.
- Text inside raster figures, figure legends, and multipanel figures (NAEGLE: 1 panel per slide). python-pptx sees pixels only.
- Whether a figure supports the headline.
- Whitespace, hierarchy, rule of thirds. The only study I opened (TORABI, 30 viewers, photographs) found no benefit for novices. No slide study found.
- Text over images, text overflow, and redundancy with narration (Mayer). These need a render or a transcript.

## 3. python-pptx experiment

I built a 4-slide deck and read it back. I also rendered it with LibreOffice and measured words with pdftotext -bbox.

- Explicit size: run.font.size returns EMU (152400 = 12 pt).
- Inherited size: None for title and body placeholders, text boxes, table cells, group children, and auto shapes. My XML resolver gave 44 pt (title), 32 and 28 pt (body levels 0 and 1), 18 pt (text box, shape). The render heights matched: 44, 32, 28, 18.
- paragraph.font.size = 30 returns 381000 while the run stays None. LibreOffice rendered 30 pt. I did not test PowerPoint (UNVERIFIED).
- Autofit: auto_size returns TEXT_TO_FIT_SHAPE. No property exposes fontScale. I injected fontScale 62500 and read it only through XML (24 pt becomes 15 pt). LibreOffice shrank the same box to 8.1 pt without a fontScale, so renderers differ.
- Bounding boxes: left, top, width, height work. A placeholder with no xfrm on the slide returned the layout values. The off-slide rectangle (right 11.5 in on a 10 in slide) is detectable. After I doubled a group's ext, the child width stayed 1828800 (true 3657600). Rotation (90.0) leaves the box unrotated.
- Text per shape: text_frame, paragraphs, runs, table cells, and group recursion work. A chart has no text_frame; chart.font.size reads only when set.
- Picture pixels: image.size returns (3840, 2160). image.dpi returns (72, 72) default metadata and is useless. Crop fractions read. Effective ppi: 200 px over 4 in = 50; 3840 px with 25% crops over 4 in = 480.
- Notes: has_notes_slide works. Reading slide.notes_slide on a slide without notes creates one (False to True).
- Alt text: no alt_text attribute. add_picture writes the file name into descr ('small.png').
- Colour: RGB reads when explicit. A theme colour returns type SCHEME, ACCENT_1, no RGB. Inherited colour returns None. slide.background.fill.type returns BACKGROUND (inherit). A no-fill shape raises TypeError on fore_color.
- font.name is None when inherited. Hidden slides have no API (XML show="0").
- Cannot read: effective size or colour after inheritance, theme-resolved RGB, rendered text extent, line count, overflow, text in images, chart text defaults, fontScale (without XML).
- Render path: soffice to PDF took 2.1 s. pdftotext -bbox gives word height equal to font size, plus line positions (3 lines in the autofit box). It drops text clipped outside the page. Carlito replaced Calibri.

## 4. Evidence notes

- 30 pt: Kawasaki states 10 slides, 20 minutes, 30 pt. I opened two secondary copies (CBS, MSDN). The original post returned 403, so "oldest attendee divided by two" is UNVERIFIED. Opened conference and institutional pages say 18-24 pt.
- Viewing distance: Rindsberg (T2) gives the 8H rule: farthest viewer at most 8 screen heights away, text at least 1/50 of screen height (10.8 pt on a 540 pt slide). He calls it a floor and recommends 24 pt. PROAV gives 6 heights for text reading and 4 for fine detail. AVIXA values: UNVERIFIED.
- Contrast formula (WCAG-DEF): L = 0.2126 R + 0.7152 G + 0.0722 B. Each channel c = s/255, then c/12.92 if c <= 0.04045, else ((c+0.055)/1.055)^2.4. Ratio = (L1+0.05)/(L2+0.05), lighter first. Do not round (4.499 fails).
- My ratios (contrast.py): white on black 21.00; #404040 on white 10.37; #767676 on white 4.54 (#777777: 4.48); yellow #FFFF00 on blue #0000FF 8.00; yellow on navy #1F3864 10.82; white on PowerPoint 2007 accent1 #4F81BD 4.03; red #FF0000 on green #00B050 1.39.
- Okabe-Ito hex (CMAP, secondary; JFLY shows the palette as an image): #000000, #E69F00, #56B4E9, #009E73, #F0E442, #0072B2, #D55E00, #CC79A7. The name-to-hex mapping comes from a search snippet. Wong 2011 was not opened. Against white, #F0E442 (1.32), #E69F00 (2.25) and #56B4E9 (2.31) fail 3:1. JFLY text gives vermilion as #FF2000, not #D55E00. JFLY advises magenta and green instead of red and green. It reports red-green colour blindness in 8% of Caucasian, 5% of Asian and 4% of African males.
- Density: no study isolates words per slide. GA13 (n=110) found assertion-evidence slides better at 10 days (t(93)=4.34, p<0.001, d=0.89). The slides differed in six ways, and the groups differed in prior knowledge. Viewers rated the text amount more appropriate for the text-heavy slides. A separate experiment (n=100) was not significant (PSU). Mayer and Fiorella 2014: redundancy 16 of 16 tests, median d 0.86. Cowan 2001: about four chunks. Miller's seven was "a rhetorical device". 6x6 and 5x5: I found no origin.
- Slides per minute: guidance only. I found no experiment.

## 5. Pages opened

- WCAG-CM https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html
- WCAG-DEF https://www.w3.org/TR/WCAG21/
- WCAG-E https://www.w3.org/WAI/WCAG21/Understanding/contrast-enhanced.html
- WCAG-NT https://www.w3.org/WAI/WCAG21/Understanding/non-text-contrast.html
- WCAG-UC https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html
- WCAG-VP https://www.w3.org/WAI/WCAG21/Understanding/visual-presentation.html
- https://www.w3.org/WAI/WCAG21/Understanding/images-of-text.html
- JFLY https://jfly.uni-koeln.de/color/ and https://jfly.uni-koeln.de/colorset/
- CMAP https://cmap-docs.readthedocs.io/en/latest/catalog/qualitative/okabeito:okabeito/
- KAW https://www.cbsnews.com/news/improve-your-powerpoint-presentations-with-guy-kawasakis-10-20-30-rule/ and https://learn.microsoft.com/archive/blogs/msdn/springboard//the-102030-rule-of-powerpoint and https://slidemodel.com/the-10-20-30-rule-of-presentations/
- UEF https://sites.uef.fi/sigmaerc2026/presentation-guidelines/
- HARV https://hsph.harvard.edu/research/health-communication/resources/slide-checklist/
- NAEGLE https://pmc.ncbi.nlm.nih.gov/articles/PMC8638955/
- MSA https://support.microsoft.com/en-us/office/make-your-powerpoint-presentations-accessible-to-people-with-disabilities-6f7772b2-2f33-4bd2-8ca7-dae3b2b3ef25
- MSF https://support.microsoft.com/en-us/powerpoint/reduce-the-file-size-of-your-powerpoint-presentations
- MSS https://support.microsoft.com/en-us/office/change-the-size-of-your-slides-040a811c-be43-40b9-8d04-0de5ed79987e
- CDC https://www.cdc.gov/healthyschools/professional_development/videos/pd201/12-developing_the_presentation.pdf
- GA13 https://www.ijee.ie/articles/Vol29-6/23_ijee2791ns.pdf
- PSU https://pure.psu.edu/en/publications/high-quality-visual-evidence-on-presentation-slides-may-offset-th-2/ and https://writing.engr.psu.edu/research.html
- Mayer 2005 and Mayer and Fiorella 2014 abstracts at cambridge.org (handbook chapter pages); Cowan 2001 abstract at https://www.cambridge.org/core/journals/behavioral-and-brain-sciences/article/magical-number-4-in-shortterm-memory-a-reconsideration-of-mental-storage-capacity/44023F1147D4A1D44BDC0AD226838496
- DUARTE https://www.duarte.com/resources/guides-tools/the-glance-test/ and https://smallwarsjournal.com/blog/do-your-slides-pass-the-glance-test
- RIND https://www.rdpslides.com/pptfaq/FAQ00125_How_big_should_text_be-_What-s_the_ideal_font_size-.htm
- PROAV https://www.proav.de/video/projectionrules.html; SLASHGEAR https://www.slashgear.com/2221483/what-is-4-6-8-rule-for-projectors/
- https://www.avixa.org/resources/standards/display-image-size-for-2d-content (no numbers)
- https://slidemodel.com/6x6-rule-powerpoint/ and https://mannerofspeaking.org/2010/03/04
- TORABI https://soad.kmutt.ac.th/wp-content/uploads/2021/06/2021INTC3.pdf
- https://python-pptx.readthedocs.io/en/latest/api/text.html

Not opened: guykawasaki.com (403), nature.com Wong 2011 (login redirect), PubMed (cookie wall), ASEE (403), creativepro (403), Eagle Hill (404), IEEE IUS (empty), web.archive.org (blocked), Netflix and SMPTE safe-area pages, Mackiewicz 2006, Savoy 2009, Microsoft 220 ppi default (search snippets only: UNVERIFIED).
