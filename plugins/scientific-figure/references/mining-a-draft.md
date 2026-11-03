# Mining a hand-made draft

A draft contains finished art and settled decisions. Both are worth more than the drawing.

## Inspect before rendering

    pdfimages -list draft.pdf     # which objects are raster; its ppi ceiling
    pdffonts   draft.pdf          # `emb no` changes the rendered weight
    pdftotext -layout draft.pdf - # the captions, which are what the art MEANS

Then render at several resolutions and **read the PNGs**. Crop regions of interest and read
those too. Never infer art from a file name.

## Cutting a glyph out, keeping vector

`pdfcrop`, `pdfjam`, `qpdf` and `mutool` are often absent. This works with `pdftocairo` + `gs`:

    # 1. clip; x and y are points from the TOP-LEFT of the page
    pdftocairo -pdf -x 227 -y 119 -W 230 -H 242 in.pdf clip.pdf
    # 2. measure the surviving ink
    gs -q -dBATCH -dNOPAUSE -sDEVICE=bbox clip.pdf
    # 3. shift it to the origin on a tight page
    gs -q -o glyph.pdf -sDEVICE=pdfwrite -dPDFSETTINGS=/prepress \
       -dDEVICEWIDTHPOINTS=<w> -dDEVICEHEIGHTPOINTS=<h> -dFIXEDMEDIA \
       -c "<</PageOffset [-<x0> -<y0>]>> setpagedevice" -f clip.pdf

`pdftocairo -x -y` measures from the TOP-left; PDF user space is bottom-left; no flip is
needed. Crop generously and let the bbox step tighten — an over-tight box silently shaves a
stroke.

Verify every cut: `pdfimages -list` should show no new rasters for line art, and the render
must be read to confirm nothing is clipped.

## Placing a glyph in a matplotlib panel

Rasterise at 600 dpi and `imshow` it into an inch-placed axes. 600 dpi into a ≤50 mm box is
inside every normal asset's ceiling. This also makes a non-embedded font moot: the text
resolves where you render and ships as pixels.

But check the *weight*. `fc-match` may resolve `Avenir-Light` to `Avenir-Roman`, so a master
renders one weight heavier than the harness text beside it.

## Traps, all found the expensive way

- **One artwork, two captions.** Pixel-sample before trusting a caption. Identical bars were
  captioned "endogenous enhancers from the top DE genes" in one column and "sequences
  designed from AI models" in another.
- **A glyph whose parts overlap in range.** A bent arrow's pixels sat inside the column range
  of the first exon block; cropping the exon at full height brought the arrow with it, and
  drew three start sites on one gene.
- **Implicit units in a column name.** `log_gap` held ε = 0 in two files and ε = 0.1 in a
  third. Recompute from stored inputs; never read such a column directly.
- **Ordinals that contradict the data.** Row labels called the second-ranked construct
  "enhancer 1". Exported filenames inherited it. Filenames do not encode rank.
- **Reproduction defects worth not copying.** Row labels overlapping their images by 3.2 pt
  because the gaps are 3.4 pt and the labels 7 pt; a scale-bar label straddling a gutter.
- **Measure the reuse ceiling per clip** before planning: its smallest cap height against
  your type floor gives the scale range. A clip needing 2.8x enlargement can never be reused.
