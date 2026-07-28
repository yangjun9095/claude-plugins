# <= 3 semantic hues. State is carried by GLYPH, never by hue alone: the
# greyscale relative luminance of ok (.544) and warn (.523) is near-identical,
# so a colour-blind or greyscale reader must still be able to tell them apart.

DARK = {
    "bg":     "#14111f",
    "ok":     "#3ddc97",
    "warn":   "#ffb000",
    "bad":    "#e8563f",
    "chrome": "#c8a2ff",
    "txt":    "#e8e3f5",
    "dim":    "#a79fc2",
    "faint":  "#8f86ad",   # raised from #7d759a, which measured CR 4.32 < 4.5
}

LIGHT = {
    "bg":     "#ffffff",
    "ok":     "#00805f",
    "warn":   "#9a6a00",
    "bad":    "#5e1500",
    "chrome": "#5b36c0",
    "txt":    "#14111f",
    "dim":    "#4a4458",
    "faint":  "#5c5570",
}


def _channel(value):
    c = value / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(hex_a, hex_b):
    la, lb = relative_luminance(hex_a), relative_luminance(hex_b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
