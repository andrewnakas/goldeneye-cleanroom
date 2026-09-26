"""Re-typeset text inside textures (text_labels.json) with our stroke font.

The background is the kept colour grid (smoothed, or a flat colour from the label entry); the
words come from the label table; the ink is drawn in our font. Result is upright; the generator's
caller flips it to GE storage order.
"""
import json
import os

import numpy as np

from cleanroom.decomp.gen import upsample_grid
from cleanroom.gfx import strokefont

HERE = os.path.dirname(os.path.abspath(__file__))
_L = None


def table():
    global _L
    if _L is None:
        _L = {k: v for k, v in json.load(open(os.path.join(HERE, "text_labels.json"), encoding="utf-8")).items() if not k.startswith("_")}
    return _L


def _fit(text, w, h, thin=False):
    th = max(0.8, h * (0.06 if thin else 0.1))
    line = strokefont.render_line(text, h, thickness=th)
    if line.shape[1] > w:
        xs = np.linspace(0, line.shape[1] - 1, w)
        x0 = np.floor(xs).astype(int)
        x1 = np.minimum(x0 + 1, line.shape[1] - 1)
        f = (xs - x0)[None, :]
        line = line[:, x0] * (1 - f) + line[:, x1] * f
    return line


def render(entry, t):
    f, w, h = t["levels"][0]
    if isinstance(entry.get("bg"), list):
        img = np.zeros((h, w, 4), np.float32)
        img[..., :3] = entry["bg"]
        img[..., 3] = 255
    else:
        # the panel colour: median of the kept grid (its cells also averaged in the old lettering)
        g = np.asarray(t["grid"], np.float32)[:, :3]
        img = np.zeros((h, w, 4), np.float32)
        img[..., :3] = np.median(g, 0) * np.linspace(1.06, 0.94, h)[:, None, None]
        img[..., 3] = 255
    lines = entry["text"].split("|")
    lh = int(h * 0.8 / len(lines))
    pad_x = max(1, w // 32)
    mask = np.zeros((h, w), np.float32)
    top = int((h - lh * len(lines)) * entry.get("valign", 0.5))
    for i, s in enumerate(lines):
        m = _fit(s, w - 2 * pad_x, lh, entry.get("thin"))
        y0 = top + i * lh
        if entry.get("align") == "right":
            x0 = w - pad_x - m.shape[1]
        elif entry.get("align") == "left":
            x0 = pad_x
        else:
            x0 = (w - m.shape[1]) // 2
        mask[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = np.maximum(mask[y0:y0 + m.shape[0], x0:x0 + m.shape[1]], m)
    fg = np.asarray(entry["fg"], np.float32)
    img[..., :3] = img[..., :3] * (1 - mask[..., None]) + fg * mask[..., None]
    return img


SEGS = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc",
        "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g"}


def seven_segment(ch, w, h, on=(235, 60, 40), off=(40, 20, 20)):
    """A lit seven-segment digit on a dark panel (upright)."""
    img = np.zeros((h, w, 4), np.float32)
    img[..., :3] = (18, 12, 12)
    img[..., 3] = 255
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x0, x1, y0, y1 = w * 0.22, w * 0.78, h * 0.1, h * 0.9
    ym = (y0 + y1) / 2
    t = max(1.0, w * 0.1)
    seg = {"a": ((x0, y0), (x1, y0)), "b": ((x1, y0), (x1, ym)), "c": ((x1, ym), (x1, y1)),
           "d": ((x0, y1), (x1, y1)), "e": ((x0, ym), (x0, y1)), "f": ((x0, y0), (x0, ym)), "g": ((x0, ym), (x1, ym))}
    for name, ((ax, ay), (bx, by)) in seg.items():
        vx, vy = bx - ax, by - ay
        ll = vx * vx + vy * vy
        u = np.clip(((xx - ax) * vx + (yy - ay) * vy) / ll, 0.12, 0.88)
        d = np.hypot(xx - (ax + u * vx), yy - (ay + u * vy))
        m = np.clip(t / 2 + 0.5 - d, 0, 1)[..., None]
        col = on if name in SEGS.get(ch, "") else off
        img[..., :3] = img[..., :3] * (1 - m) + np.asarray(col, np.float32) * m
    return img


def override(t, k):
    if t["name"].startswith("7SEG_"):
        ch = t["name"][5:]
        f, w, h = t["levels"][0]
        g = np.asarray(t["grid"], np.float32)[:, :3]
        lum = g.mean(1)
        lit, dark = g[lum.argmax()], g[lum.argmin()]
        img = seven_segment("-" if ch == "DASH" else ch, w, h, on=lit, off=dark * 0.6 + lit * 0.15)
        img[..., :3] = np.where(img[..., :3] == np.array([18, 12, 12], np.float32), dark, img[..., :3])
        return np.ascontiguousarray(img[::-1])
    e = table().get(t["name"]) or table().get(str(k))
    if e is None:
        return None
    return np.ascontiguousarray(render(e, t)[::-1])


def preview(out):
    from cleanroom.gfx import png
    T = json.load(open(os.path.join(HERE, "spec", "textures.json")))
    names = {t["name"]: k for k, t in enumerate(T)}
    tiles = []
    for key, e in table().items():
        k = names.get(key, int(key) if key.isdigit() else None)
        img = render(e, T[k])
        tiles.append(np.pad(img.repeat(3, 0).repeat(3, 1), ((2, 2), (2, 2), (0, 0))))
    W = max(t.shape[1] for t in tiles)
    sheet = np.concatenate([np.pad(t, ((0, 0), (0, W - t.shape[1]), (0, 0))) for t in tiles], 0)
    sheet[..., 3] = 255
    png.write(out, np.clip(sheet, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    import sys
    preview(sys.argv[1])
