"""Dirty room: GoldenEye ROM assets -> spec/ (kept facts only).

    python -m games.goldeneye.extract_spec textures <dirty tree> <tex_raw.bin> [--sheets DIR]

textures.json, per image-bank texture (in images.def order):
  name, retail size, header byte, levels [[format, w, h], ...], palette size (paletted),
  level-0 colour grid (4x4; 16x16 when >= 128 px) and 2-bit alpha outline (when alpha varies).
--sheets writes dirty contact sheets for looking (never committed or published).
"""
import json
import os
import re
import sys

import numpy as np

from cleanroom.decomp.spec import alpha2, grid
from cleanroom.gfx import png
from games.goldeneye import texcodec

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")


def image_names(dirty):
    out = []
    for line in open(os.path.join(dirty, "assets/images.def")):
        m = re.match(r"\s*IMAGE\(([^,]+),\s*(0x[0-9A-Fa-f]+|\d+)", line)
        if m:
            out.append((m.group(1), int(m.group(2), 0)))
    return out


def header_only(path):
    """Level-0 facts straight from the bitstream header (for files the decoder rejects)."""
    b = open(path, "rb").read()
    bits = int.from_bytes(b[1:4], "big")
    return b[0], [[bits >> 20, (bits >> 12) & 255, (bits >> 4) & 255]]


def textures(dirty, raw, sheets=None):
    names = image_names(dirty)
    recs = list(texcodec.read_raw_dump(raw))
    assert len(recs) == len(names), (len(recs), len(names))
    out, thumbs = [], []
    stats = {"zlib": 0, "levels>1": 0, "alpha": 0, "failed": 0}
    for k, ((name, size), r) in enumerate(zip(names, recs)):
        d = {"name": name, "size": size}
        if not r["levels"]:
            d["header"], d["levels"] = header_only(os.path.join(dirty, "assets/images/split", name + ".bin"))
            d["failed"] = True
            stats["failed"] += 1
            out.append(d)
            thumbs.append((name, None))
            continue
        d["header"] = r["header"]
        d["levels"] = [[lv["format"], lv["w"], lv["h"]] for lv in r["levels"]]
        if r["palette"]:
            d["palette"] = len(r["palette"])
            stats["zlib"] += 1
        if len(r["levels"]) > 1:
            stats["levels>1"] += 1
        rgba = texcodec.level_rgba(r["levels"][0], r["palette"])
        h, w = rgba.shape[:2]
        n = 16 if max(w, h) >= 128 else 4
        d["grid"] = grid(rgba, n)
        if (rgba[..., 3] < 250).any():
            d["alpha2"] = alpha2(rgba[..., 3])
            stats["alpha"] += 1
        out.append(d)
        thumbs.append((name, rgba))
    os.makedirs(SPEC, exist_ok=True)
    with open(os.path.join(SPEC, "textures.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"textures: {len(out)} ({stats})")
    if sheets:
        contact_sheets(thumbs, sheets)


def checker(h, w):
    y, x = np.mgrid[:h, :w]
    c = np.where(((x // 4) + (y // 4)) % 2, 96, 160).astype(np.uint8)
    return np.stack([c, c, c], -1)


def contact_sheets(thumbs, outdir, cell=64, cols=24, per=24 * 16):
    """Dirty contact sheets: each tile = level 0 scaled to fit 64x64 over a checkerboard."""
    from cleanroom.gfx import strokefont  # noqa: F401 (labels drawn as index numbers below)
    os.makedirs(outdir, exist_ok=True)
    for s in range(0, len(thumbs), per):
        chunk = thumbs[s:s + per]
        rows = (len(chunk) + cols - 1) // cols
        sheet = np.zeros((rows * (cell + 10), cols * cell, 3), np.uint8)
        for i, (name, rgba) in enumerate(chunk):
            y0, x0 = (i // cols) * (cell + 10), (i % cols) * cell
            if rgba is None:
                sheet[y0:y0 + cell, x0:x0 + cell] = (255, 0, 255)
                continue
            h, w = rgba.shape[:2]
            sc = max(1, min(cell // max(w, 1), cell // max(h, 1))) if max(w, h) <= cell else 0
            if sc:
                img = rgba.repeat(sc, 0).repeat(sc, 1)
            else:
                ys = (np.arange(min(cell, h * cell // max(w, h))) * max(w, h) // cell).clip(0, h - 1)
                xs = (np.arange(min(cell, w * cell // max(w, h))) * max(w, h) // cell).clip(0, w - 1)
                img = rgba[ys][:, xs]
            ih, iw = img.shape[:2]
            a = img[..., 3:4].astype(np.float32) / 255
            bg = checker(ih, iw).astype(np.float32)
            sheet[y0:y0 + ih, x0:x0 + iw] = (img[..., :3] * a + bg * (1 - a)).astype(np.uint8)
            _label(sheet, x0 + 1, y0 + cell + 1, name if name.isdigit() else str(s + i))
        png.write(os.path.join(outdir, "tex_%04d.png" % s), sheet)
    print("sheets ->", outdir)


_DIG = {"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111",
        "4": "101101111001001", "5": "111100111001111", "6": "111100111101111", "7": "111001001001001",
        "8": "111101111101111", "9": "111101111001111"}


def _label(img, x, y, s):
    for c in s:
        bits = _DIG[c]
        for k, b in enumerate(bits):
            if b == "1":
                yy, xx = y + (k // 3) * 2, x + (k % 3) * 2
                img[yy:yy + 2, xx:xx + 2] = (255, 255, 0)
        x += 8


def main(argv):
    if argv[0] == "textures":
        sheets = argv[argv.index("--sheets") + 1] if "--sheets" in argv else None
        textures(argv[1], argv[2], sheets)


if __name__ == "__main__":
    main(sys.argv[1:])
