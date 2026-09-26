"""Textures embedded inside prop model files (not in the image bank).

Three props carry raw texture data in a PADDING_0x... array of their Model.c (decomp converter
output): the legal page, the 3D GoldenEye logo and the Nintendo logo. Everything else in those
files is geometry/display lists (kept). The pixel regions are regenerated here:

  legalpage   0x090 RGBA16 32x32   rating badge "4"            -> drawn
              0x898 I4    128x32   GOLDENEYE 007 wordmark       -> re-typeset
              0x10A0 I4    80x24   signature                    -> our own scribbled signature
              0x1468 I4   128x24   signature                    -> our own scribbled signature
              0x1A70 I4    48x64   developer badge              -> drawn frame + typeset RARE
  goldeneyelogo 0x068 RGBA16 32x32 + mips, 0xB28 1x1   gold gradient  -> 4x4 grid (kept) + mips
  nintendologo  0x408 I8 32x32     chrome environment map       -> 4x4 grid (kept)

GE stores texture rows bottom first; pictures are drawn upright and flipped.

    python -m games.goldeneye.embedded extract <dirty>          -> spec/embedded.json (grids only)
    python -m games.goldeneye.embedded build <dirty> <clean>
"""
import json
import os
import re
import sys

import numpy as np

from cleanroom.decomp.gen import from_digest
from cleanroom.decomp.spec import grid
from cleanroom.gfx import facepaint, strokefont
from games.goldeneye.fonts import parse_u32_arrays

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec", "embedded.json")

REGIONS = {
    "legalpage": [("badge4", 0x090, "rgba16", 32, 32), ("wordmark", 0x898, "i4", 128, 32),
                  ("sig1", 0x10A0, "i4", 80, 24), ("sig2", 0x1468, "i4", 128, 24),
                  ("devbadge", 0x1A70, "i4", 48, 64)],
    "goldeneyelogo": [("gold", 0x068, "rgba16mip", 32, 32), ("gold1x1", 0xB28, "rgba16", 1, 1)],
    "nintendologo": [("chrome", 0x408, "i8", 32, 32)],
}


def _padding(src):
    a = parse_u32_arrays(src)
    name = max((n for n in a if n.startswith("PADDING_0x")), key=lambda n: len(a[n]))
    return name, int(name.split("0x")[1], 16), bytearray(np.asarray(a[name], ">u4").tobytes())


def _nbytes(fmt, w, h):
    if fmt == "rgba16mip":
        n, s = 0, w
        while s >= 1:
            n += s * s * 2
            s //= 2
        return n
    return {"rgba16": w * h * 2, "i4": w * h // 2, "i8": w * h}[fmt]


def _decode(fmt, b, w, h):
    if fmt.startswith("rgba16"):
        v = np.frombuffer(bytes(b[:w * h * 2]), ">u2").astype(np.uint32)
        rgb = np.stack([(v >> 11 & 31) * 255 // 31, (v >> 6 & 31) * 255 // 31, (v >> 1 & 31) * 255 // 31, (v & 1) * 255], -1)
        return rgb.reshape(h, w, 4).astype(np.uint8)
    if fmt == "i8":
        i = np.frombuffer(bytes(b[:w * h]), np.uint8).reshape(h, w)
    else:
        bb = np.frombuffer(bytes(b[:w * h // 2]), np.uint8)
        i = (np.stack([bb >> 4, bb & 15], -1).reshape(h, w) * 17).astype(np.uint8)
    return np.stack([i, i, i, np.full_like(i, 255)], -1)


def extract(dirty):
    out = {}
    for model, regs in REGIONS.items():
        src = open(os.path.join(dirty, f"assets/obseg/prop/{model}/Model.c")).read()
        name, base, data = _padding(src)
        for key, off, fmt, w, h in regs:
            o = off - base
            img = _decode(fmt, data[o:o + _nbytes(fmt, w, h)], w, h)
            out[key] = {"model": model, "grid": grid(img, 4)}
    json.dump(out, open(SPEC, "w"), indent=0)
    print(f"embedded: {len(out)} regions -> {SPEC}")


# ------------------------------------------------------------------ our drawings (upright)

def _text(s, w, h, th=None, slant=0.0):
    m = strokefont.render_line(s, h, thickness=th if th else max(0.8, h * 0.09))
    if slant:
        out = np.zeros_like(m)
        for y in range(m.shape[0]):
            sh = int(round(slant * (m.shape[0] - y)))
            out[y, sh:] = m[y, :m.shape[1] - sh] if sh else m[y]
        m = out
    if m.shape[1] > w:
        m = m[:, np.clip(np.linspace(0, m.shape[1] - 1, w).astype(int), 0, m.shape[1] - 1)]
    return m


def _place(canvas, m, cx, cy):
    h, w = m.shape
    y0, x0 = int(cy - h / 2), int(cx - w / 2)
    ys, xs = slice(max(0, y0), min(canvas.shape[0], y0 + h)), slice(max(0, x0), min(canvas.shape[1], x0 + w))
    canvas[ys, xs] = np.maximum(canvas[ys, xs], m[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0])


def signature(text, w, h, seed):
    """A quick hand-written looking signature: our stroke letters, slanted, jittered, underlined."""
    rng = np.random.default_rng(seed)
    c = np.zeros((h, w), np.float32)
    m = _text(text, int(w * 0.95), int(h * 0.75), th=1.0, slant=0.35)
    # wobble rows a little
    for y in range(m.shape[0]):
        m[y] = np.roll(m[y], int(rng.integers(-1, 2)))
    _place(c, m, w / 2, h * 0.45)
    xs = np.arange(int(w * 0.1), int(w * 0.9))
    ys = (h * 0.85 + 1.5 * np.sin(xs / w * 7 + seed)).astype(int)
    c[np.clip(ys, 0, h - 1), xs] = 1.0
    return c


def draw(key, w, h):
    """Upright grey (I4) mask or RGBA image for each legal-page region."""
    if key == "wordmark":
        c = np.zeros((h, w), np.float32)
        _place(c, _text("GOLDENEYE", int(w * 0.6), int(h * 0.5)), w * 0.33, h * 0.55)
        _place(c, _text("007", int(w * 0.35), int(h * 0.85), th=h * 0.07), w * 0.8, h * 0.5)
        return c
    if key == "sig1":
        return signature("J. Bond", w, h, 3)
    if key == "sig2":
        return signature("M. Moneypenny", w, h, 5)
    if key == "devbadge":
        ops = [{"rect": [0.05, 0.03, 0.95, 0.97], "c": [255, 255, 255]},
               {"rect": [0.12, 0.07, 0.88, 0.93], "c": [0, 0, 0]}]
        img = facepaint.render({"base": [0, 0, 0], "ops": ops}, w, h)[..., 0] / 255
        _place(img, _text("RARE", int(w * 0.7), int(h * 0.14)), w / 2, h * 0.17)
        _place(img, _text("R", int(w * 0.6), int(h * 0.55), th=h * 0.07), w / 2, h * 0.6)
        return img
    if key == "badge4":
        ops = [{"e": [0.5, 0.5, 0.46, 0.46], "c": [210, 30, 30]}, {"e": [0.5, 0.5, 0.36, 0.36], "c": [250, 250, 250]}]
        img = facepaint.render({"base": [255, 255, 255], "ops": ops}, w, h)
        m = np.zeros((h, w), np.float32)
        _place(m, _text("4", int(w * 0.5), int(h * 0.55), th=2.0), w / 2, h / 2)
        img[..., :3] = img[..., :3] * (1 - m[..., None]) + np.array([210, 30, 30]) * m[..., None]
        img[..., 3] = 255
        return img
    return None


def _encode(fmt, img):
    if fmt.startswith("rgba16"):
        p = np.clip(img, 0, 255).astype(np.uint32).reshape(-1, 4)
        v = ((p[:, 0] >> 3) << 11) | ((p[:, 1] >> 3) << 6) | ((p[:, 2] >> 3) << 1) | (p[:, 3] >= 128)
        return v.astype(">u2").tobytes()
    i = img if img.ndim == 2 else img[..., :3].mean(-1)
    if fmt == "i8":
        return np.clip(i, 0, 255).astype(np.uint8).tobytes()
    q = np.clip(np.round(i / 17.0), 0, 15).astype(np.uint8)
    return ((q[:, 0::2] << 4) | q[:, 1::2]).tobytes()


def region_pixels(key, fmt, w, h, spec):
    """Generated bytes for one region (storage order)."""
    pic = draw(key, w, h)
    if pic is not None and pic.ndim == 2:
        img = np.clip(pic * 255, 0, 255)
    elif pic is not None:
        img = pic
    else:
        img = from_digest("ge/embedded/" + key, {"w": w, "h": h, "grid": spec[key]["grid"]}).astype(np.float32)
    if fmt == "rgba16mip":
        from games.goldeneye.generate import downscale
        out, s = b"", w
        base = img.astype(np.uint8)
        while s >= 1:
            lvl = base if s == w else downscale(base, s, s)
            out += _encode("rgba16", lvl[::-1])
            s //= 2
        return out
    return _encode(fmt, img[::-1])


def build(dirty, clean):
    spec = json.load(open(SPEC))
    n = 0
    for model, regs in REGIONS.items():
        path = os.path.join(clean, f"assets/obseg/prop/{model}/Model.c")
        src = open(os.path.join(dirty, f"assets/obseg/prop/{model}/Model.c")).read()
        name, base, data = _padding(src)
        for key, off, fmt, w, h in regs:
            o = off - base
            new = region_pixels(key, fmt, w, h, spec)
            assert len(new) == _nbytes(fmt, w, h), (key, len(new))
            data[o:o + len(new)] = new
            n += 1
        words = np.frombuffer(bytes(data), ">u4")
        body = ", ".join("0x%08X" % v for v in words)
        src = re.sub(r"(u32\s+" + name + r"\s*\[[^\]]*\]\s*=\s*\{)(.*?)(\};)",
                     lambda m: m.group(1) + body + m.group(3), src, count=1, flags=re.S)
        open(path, "w", newline="\n").write(src)
    print(f"embedded: {n} regions regenerated in {len(REGIONS)} prop models")


def streams(tree):
    """(label, bytes) of every embedded region, for the taint scan."""
    for model, regs in REGIONS.items():
        src = open(os.path.join(tree, f"assets/obseg/prop/{model}/Model.c")).read()
        name, base, data = _padding(src)
        for key, off, fmt, w, h in regs:
            o = off - base
            yield f"embedded.{model}.{key}", bytes(data[o:o + _nbytes(fmt, w, h)])


def preview(out):
    from cleanroom.gfx import png
    spec = json.load(open(SPEC))
    tiles = []
    for model, regs in REGIONS.items():
        for key, off, fmt, w, h in regs:
            if fmt == "rgba16mip" or w == 1:
                continue
            b = region_pixels(key, fmt, w, h, spec)
            img = _decode(fmt, bytearray(b), w, h)[::-1]
            tiles.append(np.pad(img.repeat(3, 0).repeat(3, 1), ((4, 4), (4, 4), (0, 0)), constant_values=90))
    W = max(t.shape[1] for t in tiles)
    sh = np.concatenate([np.pad(t, ((0, 0), (0, W - t.shape[1]), (0, 0)), constant_values=90) for t in tiles])
    sh[..., 3] = 255
    png.write(out, sh.astype(np.uint8))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "extract":
        extract(sys.argv[2])
    elif cmd == "build":
        build(sys.argv[2], sys.argv[3])
    else:
        preview(sys.argv[2])
