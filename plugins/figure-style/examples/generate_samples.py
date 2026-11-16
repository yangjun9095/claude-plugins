#!/usr/bin/env python3
"""Generate good-vs-bad sample figures to demonstrate the figure-style plugin.

Run:  python generate_samples.py
Out:  sample_good_*.png + sample_good_*.pdf (dual-save),
      sample_bad_*.png (no PDF for bad examples)

Each pair shows the same data — one with publication styling, one without.
Good examples are saved as both PNG and PDF (with editable text).
"""

import sys
from pathlib import Path

# Add scripts dir for helpers
_scripts = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_scripts))

import numpy as np

np.random.seed(42)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from figure_helpers import (
    apply_style,
    save_figure,
    verify_figure,
    get_palette,
    strip_embedding_axes,
    PALETTE_QUAL,
)

OUT = Path(__file__).resolve().parent


# ============================================================================
# Synthetic data
# ============================================================================

def _make_clusters(n_per=200, k=5):
    """Generate clustered 2D data."""
    centers = np.array([
        [2, 3], [-1, -2], [4, -1], [-3, 2], [0, 5]
    ])[:k]
    labels = np.repeat(np.arange(k), n_per)
    X = np.vstack([
        np.random.randn(n_per, 2) * 0.6 + c
        for c in centers
    ])
    return X, labels


def _make_heatmap_data(rows=20, cols=15):
    """Generate expression-like heatmap data."""
    data = np.random.randn(rows, cols)
    # Add block structure
    data[:8, :5] += 3
    data[10:, 8:] += 2.5
    data[5:12, 5:10] -= 2
    return data


# ============================================================================
# 1. Scatter plot — Good vs Bad
# ============================================================================

def scatter_bad():
    """BAD: default matplotlib, no labels, no alpha, default colors."""
    X, labels = _make_clusters()
    fig, ax = plt.subplots()  # default tiny size
    for k in range(5):
        mask = labels == k
        ax.scatter(X[mask, 0], X[mask, 1])  # no label, no alpha, default colors
    ax.set_title("Clusters")  # vague title
    # no axis labels, no legend
    fig.savefig(OUT / "sample_bad_scatter.png", dpi=72)  # low DPI
    plt.close(fig)
    print(f"  Bad scatter:  {OUT / 'sample_bad_scatter.png'}")


def scatter_good():
    """GOOD: UMAP with stripped axes, compact, palette, legend outside."""
    apply_style()
    X, labels = _make_clusters()
    names = ["cluster A", "cluster B", "cluster C", "cluster D", "cluster E"]
    palette = get_palette(5)

    fig, ax = plt.subplots(figsize=(4, 3.5))
    for k in range(5):
        mask = labels == k
        ax.scatter(X[mask, 0], X[mask, 1], c=palette[k], label=names[k],
                   s=5, alpha=0.6, edgecolors="none", rasterized=True)
    ax.set_title("embedding by cluster")
    # UMAP axes are arbitrary — strip them
    strip_embedding_axes(ax)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left",
              markerscale=2, frameon=False)
    save_figure(fig, OUT / "sample_good_scatter.png", dpi=300)
    plt.close(fig)


# ============================================================================
# 2. Heatmap — Good vs Bad
# ============================================================================

def heatmap_bad():
    """BAD: colorbar overlaps, no labels, jet colormap, tiny fonts."""
    data = _make_heatmap_data()
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(data, cmap="jet", aspect="auto")  # jet = bad
    fig.colorbar(im, ax=ax, shrink=0.6)  # may overlap
    ax.set_title("Heatmap")
    # no axis labels, no colorbar label
    fig.savefig(OUT / "sample_bad_heatmap.png", dpi=72, bbox_inches="tight")
    plt.close(fig)
    print(f"  Bad heatmap:  {OUT / 'sample_bad_heatmap.png'}")


def heatmap_good():
    """GOOD: viridis, dedicated colorbar axes, lowercase labels, compact."""
    apply_style()
    data = _make_heatmap_data()

    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(data, cmap="viridis", aspect="auto")
    ax.set_xlabel("genes")
    ax.set_ylabel("cells")

    # Dedicated colorbar axes — never overlaps
    fig.subplots_adjust(right=0.85)
    cbar_ax = fig.add_axes([0.88, 0.15, 0.02, 0.7])
    fig.colorbar(im, cax=cbar_ax, label="expression (z-score)")

    save_figure(fig, OUT / "sample_good_heatmap.png", dpi=300)
    plt.close(fig)


# ============================================================================
# 3. Multi-panel — Good vs Bad
# ============================================================================

def multipanel_bad():
    """BAD: inconsistent, missing labels, no shared axes."""
    X, labels = _make_clusters()
    fig, axes = plt.subplots(1, 3, figsize=(12, 3))
    for i, ax in enumerate(axes):
        mask = labels == i
        ax.scatter(X[mask, 0], X[mask, 1], s=2)
        ax.set_title(f"Group {i}")
        # Each axis has different ranges — no sharey/sharex
        # Missing labels on panels 1 and 2
    axes[0].set_xlabel("x")
    axes[0].set_ylabel("y")
    fig.savefig(OUT / "sample_bad_multipanel.png", dpi=72, bbox_inches="tight")
    plt.close(fig)
    print(f"  Bad multi:    {OUT / 'sample_bad_multipanel.png'}")


def multipanel_good():
    """GOOD: shared axes, consistent color, lowercase labels, compact."""
    apply_style()
    X, labels = _make_clusters()
    palette = get_palette(5)
    names = ["neural crest", "somites", "PSM"]

    fig, axes = plt.subplots(1, 3, figsize=(9, 3), sharex=True, sharey=True)
    for i, ax in enumerate(axes):
        # Plot all in grey background, highlight one group
        ax.scatter(X[:, 0], X[:, 1], c="#E5E7EB", s=1, alpha=0.3,
                   edgecolors="none", rasterized=True)
        mask = labels == i
        ax.scatter(X[mask, 0], X[mask, 1], c=palette[i], s=3, alpha=0.7,
                   edgecolors="none", rasterized=True, label=names[i])
        ax.set_title(names[i])
        ax.set_xlabel("UMAP 1")
    axes[0].set_ylabel("UMAP 2")
    fig.align_ylabels()
    save_figure(fig, OUT / "sample_good_multipanel.png", dpi=300)
    plt.close(fig)


# ============================================================================
# Main
# ============================================================================

def main():
    print("Generating BAD examples (no style)...")
    scatter_bad()
    heatmap_bad()
    multipanel_bad()

    print("\nGenerating GOOD examples (with figure-style)...")
    scatter_good()
    heatmap_good()
    multipanel_good()

    print("\nDone. Compare good vs bad in the examples/ directory.")


if __name__ == "__main__":
    main()
