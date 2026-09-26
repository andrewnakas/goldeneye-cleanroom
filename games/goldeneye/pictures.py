"""Menu pictures drawn from our own descriptions (picture_briefs.json): character/Bond portraits,
mission and multiplayer thumbnails, the dossier stamps and the service crest.

The game stores these pictures as tiles (portraits: four 65x65 quadrants; mission thumbnails: two
128x64 halves; stamps: two 95x32 halves) and, like every GE texture, bottom row first. We paint
the whole picture upright, cut it into the tiles and flip each tile.

    python -m games.goldeneye.pictures preview <out.png>
"""
import json
import math
import os
import re
import sys

import numpy as np

from cleanroom.gfx import facepaint, strokefont

HERE = os.path.dirname(os.path.abspath(__file__))
BRIEFS = os.path.join(HERE, "picture_briefs.json")

_B = None


def briefs():
    global _B
    if _B is None:
        _B = json.load(open(BRIEFS))
    return _B


# ------------------------------------------------------------------ portraits

def _hat(kind, tone):
    if kind == "cap":        # peaked military cap
        return [{"poly": [[0.26, 0.26], [0.30, 0.10], [0.70, 0.10], [0.74, 0.26]], "c": tone},
                {"e": [0.5, 0.27, 0.27, 0.05], "c": [max(0, tone[0] - 40)] * 3},
                {"rect": [0.44, 0.14, 0.56, 0.19], "c": [220, 220, 220]}]
    if kind == "tophat":
        return [{"rect": [0.33, 0.02, 0.67, 0.25], "c": tone},
                {"rect": [0.33, 0.19, 0.67, 0.23], "c": [230, 230, 230]},
                {"e": [0.5, 0.26, 0.30, 0.04], "c": tone}]
    if kind == "bowler":
        return [{"e": [0.5, 0.24, 0.21, 0.14], "c": tone},
                {"e": [0.5, 0.29, 0.29, 0.04], "c": tone}]
    return []


def _hair(style, tone):
    t = tone
    if style == "bald":
        return [], []
    back, front = [], []
    if style in ("long", "bob"):
        back = [{"e": [0.5, 0.45, 0.28, 0.34 if style == "long" else 0.27], "c": t}]
        if style == "long":
            back.append({"rect": [0.24, 0.45, 0.76, 0.86], "c": t})
    if style == "flattop":
        front = [{"rect": [0.30, 0.14, 0.70, 0.30], "c": t}]
    elif style == "curly":
        front = [{"e": [0.5 + 0.13 * math.cos(a), 0.25 + 0.06 * math.sin(a), 0.09, 0.07], "c": t}
                 for a in np.linspace(0, 2 * math.pi, 9)[:-1]] + [{"e": [0.5, 0.25, 0.2, 0.09], "c": t}]
    elif style == "slick":
        front = [{"poly": [[0.29, 0.40], [0.30, 0.22], [0.42, 0.15], [0.64, 0.16], [0.72, 0.26], [0.71, 0.40],
                           [0.66, 0.28], [0.40, 0.26]], "c": t}]
    elif style == "wavy":
        front = [{"poly": [[0.29, 0.42], [0.29, 0.22], [0.40, 0.14], [0.62, 0.14], [0.72, 0.24], [0.71, 0.42],
                           [0.66, 0.30], [0.55, 0.27], [0.47, 0.31], [0.38, 0.27]], "c": t}]
    elif style == "receding":
        front = [{"poly": [[0.29, 0.44], [0.30, 0.30], [0.36, 0.24], [0.40, 0.33], [0.33, 0.44]], "c": t},
                 {"poly": [[0.71, 0.44], [0.70, 0.30], [0.64, 0.24], [0.60, 0.33], [0.67, 0.44]], "c": t}]
    elif style in ("long", "bob"):
        front = [{"poly": [[0.27, 0.46], [0.29, 0.22], [0.42, 0.13], [0.62, 0.13], [0.73, 0.24], [0.73, 0.46],
                           [0.64, 0.27], [0.36, 0.27]], "c": t}]
    else:  # short
        front = [{"poly": [[0.29, 0.38], [0.30, 0.21], [0.42, 0.15], [0.60, 0.15], [0.71, 0.22], [0.71, 0.38],
                           [0.66, 0.27], [0.36, 0.27]], "c": t}]
    return back, front


def portrait_brief(p):
    skin = [p.get("skin", 196)] * 3
    shade = [max(0, skin[0] - 45)] * 3
    hair = [p.get("hair_tone", 60)] * 3
    suit = p.get("suit", "tux")
    ops = []
    back, front = _hair(p.get("hair", "short"), hair)
    ops += back
    # shoulders and clothes
    cloth = {"tux": 35, "military": 70, "jacket": 110, "dress": 45, "shirt": 170, "coat": 90}[suit]
    ops.append({"poly": [[0.02, 1.0], [0.10, 0.82], [0.30, 0.74], [0.70, 0.74], [0.90, 0.82], [0.98, 1.0]],
                "c": [cloth] * 3})
    ops.append({"rect": [0.42, 0.58, 0.58, 0.80], "c": shade})                       # neck
    if suit in ("tux", "jacket", "coat"):
        ops.append({"poly": [[0.38, 0.74], [0.5, 0.97], [0.62, 0.74]], "c": [235, 235, 235]})   # shirt
        if suit == "tux":
            ops.append({"poly": [[0.43, 0.78], [0.5, 0.81], [0.57, 0.78], [0.57, 0.84], [0.5, 0.81], [0.43, 0.84]],
                        "c": [20, 20, 20]})                                         # bow tie
        else:
            ops.append({"poly": [[0.48, 0.78], [0.52, 0.78], [0.54, 0.97], [0.46, 0.97]], "c": [60, 60, 60]})
    if suit == "military":
        ops += [{"rect": [0.12, 0.80, 0.30, 0.84], "c": [200, 200, 200]},
                {"rect": [0.70, 0.80, 0.88, 0.84], "c": [200, 200, 200]},
                {"rect": [0.62, 0.88, 0.66, 0.93], "c": [220, 220, 220]},
                {"rect": [0.68, 0.88, 0.72, 0.93], "c": [180, 180, 180]},
                {"poly": [[0.40, 0.74], [0.5, 0.86], [0.60, 0.74]], "c": [140, 140, 140]}]
    if suit == "dress":
        ops.append({"poly": [[0.34, 0.74], [0.5, 0.88], [0.66, 0.74]], "c": skin})
    if suit == "shirt":
        ops.append({"poly": [[0.40, 0.74], [0.5, 0.82], [0.60, 0.74]], "c": shade})
    # head
    wid = p.get("head_w", 0.2)
    ops += [{"e": [0.5 - wid - 0.005, 0.47, 0.035, 0.06], "c": shade},
            {"e": [0.5 + wid + 0.005, 0.47, 0.035, 0.06], "c": shade},
            {"e": [0.5, 0.44, wid, 0.25], "c": skin}]
    ops.append({"e": [0.5, 0.60, wid * 0.8, 0.08], "c": [min(255, skin[0] + 0)] * 3})
    ops += front
    for x in (0.42, 0.58):
        ops.append({"eye": {"c": [x, 0.45], "r": [0.045, 0.022], "iris": [70, 70, 70], "irisr": 0.55, "border": 0.2}})
        ops.append({"line": [[x - 0.05, 0.405 - p.get("brow", 0)], [x + 0.05, 0.40]], "w": 0.018,
                    "c": [max(0, hair[0] - 10)] * 3})
    ops.append({"line": [[0.5, 0.46], [0.49, 0.54], [0.52, 0.545]], "w": 0.014, "c": shade})       # nose
    if p.get("teeth"):
        ops += [{"rect": [0.42, 0.585, 0.58, 0.62], "c": [240, 240, 240]}] + \
               [{"line": [[x, 0.585], [x, 0.62]], "w": 0.008, "c": [120, 120, 120]} for x in (0.46, 0.5, 0.54)]
    else:
        ops.append({"arc": [0.5, 0.575, 0.06, 0.02 * p.get("smile", 1), 20, 160], "w": 0.014, "c": [110, 90, 90]})
    if p.get("moustache"):
        ops.append({"poly": [[0.44, 0.565], [0.5, 0.55], [0.56, 0.565], [0.55, 0.575], [0.45, 0.575]], "c": hair})
    if p.get("glasses"):
        ops += [{"ring": [x, 0.45, 0.06, 0.04], "w": 0.012, "c": [30, 30, 30]} for x in (0.42, 0.58)]
        ops.append({"line": [[0.48, 0.445], [0.52, 0.445]], "w": 0.012, "c": [30, 30, 30]})
    if p.get("scar"):
        ops.append({"line": [[0.37, 0.40], [0.40, 0.47], [0.43, 0.53]], "w": 0.012, "c": [120, 110, 110]})
    if p.get("facepaint"):
        ops += [{"e": [x, 0.45, 0.06, 0.05], "c": [30, 30, 30]} for x in (0.42, 0.58)] + \
               [{"e": [0.5, 0.52, 0.03, 0.02], "c": [30, 30, 30]},
                {"rect": [0.43, 0.575, 0.57, 0.60], "c": [235, 235, 235]}]
    ops += _hat(p.get("hat"), [p.get("hat_tone", 40)] * 3)
    if p.get("silhouette"):
        ops = [{"e": [0.5, 0.42, 0.2, 0.25], "c": [40, 40, 40]},
               {"poly": [[0.02, 1.0], [0.10, 0.82], [0.30, 0.74], [0.70, 0.74], [0.90, 0.82], [0.98, 1.0]],
                "c": [40, 40, 40]}]
    return {"base": {"grad": [[p.get("bg", 215)] * 3, [max(0, p.get("bg", 215) - 70)] * 3]}, "ops": ops}


def paint_portrait(p, w, h):
    img = facepaint.render(portrait_brief(p), w, h, seed=7)
    if p.get("silhouette"):
        m = strokefont.render("?", w // 2, h // 2)
        y0, x0 = h // 5, w // 4
        img[y0:y0 + m.shape[0], x0:x0 + m.shape[1], :3] = img[y0:y0 + m.shape[0], x0:x0 + m.shape[1], :3] * (1 - m[..., None]) + 235 * m[..., None]
    return img


# ------------------------------------------------------------------ scenes (mission thumbnails)

def paint_scene(name, w, h):
    b = briefs()["scenes"].get(name)
    if b is None:
        b = briefs()["scenes"]["_default"]
    img = facepaint.render(b, w, h, seed=hash(name) & 0xffff)
    rng = np.random.default_rng(len(name) * 131)
    img[..., :3] *= (1 + 0.06 * rng.standard_normal((h, w, 1)))      # photo grain
    return np.clip(img, 0, 255)


# ------------------------------------------------------------------ stamps and crest

def paint_stamp(text, w, h):
    """White stamp lettering with a frame on transparent (the game tints it)."""
    img = np.zeros((h, w, 4), np.float32)
    m = strokefont.render_line(text, int(h * 0.72), thickness=max(1.6, h * 0.09))
    if m.shape[1] > w - 8:
        xs = np.linspace(0, m.shape[1] - 1, w - 8)
        m = m[:, np.clip(xs.astype(int), 0, m.shape[1] - 1)]
    y0, x0 = (h - m.shape[0]) // 2, (w - m.shape[1]) // 2
    a = np.zeros((h, w), np.float32)
    a[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m
    frame = np.zeros((h, w), np.float32)
    frame[1:3, 2:-2] = frame[-3:-1, 2:-2] = 1
    frame[1:-1, 2:4] = frame[1:-1, -4:-2] = 1
    a = np.maximum(a, frame)
    rng = np.random.default_rng(len(text))
    a *= (rng.random((h, w)) > 0.12)             # worn ink
    img[..., :3] = 255
    img[..., 3] = a * 255
    return img


def paint_crest(w, h):
    """A heraldic shield with a crown above and two supporters' silhouettes (our own design)."""
    ops = [
        {"poly": [[0.35, 0.30], [0.65, 0.30], [0.65, 0.62], [0.5, 0.80], [0.35, 0.62]], "c": [255, 255, 255]},
        {"poly": [[0.39, 0.34], [0.61, 0.34], [0.61, 0.60], [0.5, 0.74], [0.39, 0.60]], "c": [0, 0, 0]},
        {"line": [[0.5, 0.35], [0.5, 0.72]], "w": 0.02, "c": [255, 255, 255]},
        {"line": [[0.40, 0.48], [0.60, 0.48]], "w": 0.02, "c": [255, 255, 255]},
        {"poly": [[0.38, 0.27], [0.40, 0.16], [0.45, 0.22], [0.5, 0.13], [0.55, 0.22], [0.60, 0.16], [0.62, 0.27]],
         "c": [255, 255, 255]},
        {"e": [0.24, 0.52, 0.08, 0.20], "c": [255, 255, 255]}, {"e": [0.24, 0.30, 0.06, 0.06], "c": [255, 255, 255]},
        {"e": [0.76, 0.52, 0.08, 0.20], "c": [255, 255, 255]}, {"e": [0.76, 0.30, 0.06, 0.06], "c": [255, 255, 255]},
        {"arc": [0.5, 0.80, 0.30, 0.08, 10, 170], "w": 0.03, "c": [255, 255, 255]},
    ]
    img = facepaint.render({"base": [0, 0, 0], "ops": ops}, w, h)
    lum = img[..., :3].mean(-1)
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = 255
    out[..., 3] = np.clip(lum, 0, 255)
    return out


# ------------------------------------------------------------------ tiling

QUAD = {"UL": (0, 0), "UR": (0, 1), "LL": (1, 0), "LR": (1, 1)}


def _tile(full, row, col, w, h, rows, cols):
    H, W = full.shape[:2]
    y0 = 0 if row == 0 else H - h
    x0 = 0 if col == 0 else W - w
    return full[y0:y0 + h, x0:x0 + w]


def storage(img):
    """Upright picture -> GE storage order (bottom row first)."""
    return np.ascontiguousarray(img[::-1])


_cache = {}


def override(t, all_tex):
    """Level-0 RGBA (storage order) for a menu picture texture, or None."""
    name = t["name"]
    f, w, h = t["levels"][0]
    P = briefs()
    m = re.fullmatch(r"([A-Z0-9]+)_(UL|UR|LL|LR)", name)
    if m and m.group(1) in P["portraits"]:
        key = m.group(1)
        if key not in _cache:
            _cache[key] = paint_portrait(P["portraits"][key], 2 * w - 1, 2 * h - 1)
        r, c = QUAD[m.group(2)]
        return storage(_tile(_cache[key], r, c, w, h, 2, 2))
    if m and m.group(1) == "MI6":
        if "MI6" not in _cache:
            _cache["MI6"] = paint_crest(2 * w - 1, 2 * h - 1)
        r, c = QUAD[m.group(2)]
        return storage(_tile(_cache["MI6"], r, c, w, h, 2, 2))
    m = re.fullmatch(r"([A-Z]+I*)_(U|L)", name)
    if m and (m.group(1) in P["scenes"]):
        key = "scene:" + m.group(1)
        if key not in _cache:
            _cache[key] = paint_scene(m.group(1), w, 2 * h)
        full = _cache[key]
        return storage(full[:h] if m.group(2) == "U" else full[h:])
    m = re.fullmatch(r"MP_([A-Z0-9]+)", name)
    if m:
        return storage(paint_scene(P["mp_scene"].get(m.group(1), m.group(1)), w, h))
    m = re.fullmatch(r"([A-Z]+)_(L|R)", name)
    if m and m.group(1) in P["stamps"]:
        key = "stamp:" + m.group(1)
        if key not in _cache:
            _cache[key] = paint_stamp(P["stamps"][m.group(1)], 2 * w, h)
        full = _cache[key]
        return storage(full[:, :w] if m.group(2) == "L" else full[:, w:])
    if name == "MI6":
        return storage(paint_crest(w, h))
    return None


def preview(out):
    """Clean preview sheet: every picture assembled upright."""
    from cleanroom.gfx import png
    P = briefs()
    tiles = [paint_portrait(p, 129, 129) for p in P["portraits"].values()]
    tiles += [paint_scene(s, 128, 128) for s in P["scenes"] if not s.startswith("_")]
    tiles.append(paint_crest(129, 129))
    cols = 8
    rows = (len(tiles) + cols - 1) // cols
    sheet = np.zeros((rows * 132, cols * 132, 4), np.float32)
    for i, t in enumerate(tiles):
        y, x = (i // cols) * 132, (i % cols) * 132
        sheet[y:y + t.shape[0], x:x + t.shape[1]] = t
    sheet[..., 3] = 255
    stamps = [paint_stamp(s, 190, 32) for s in P["stamps"].values()]
    strip = np.concatenate([np.pad(s, ((2, 2), (2, 2), (0, 0))) for s in stamps], 0)
    strip[..., :3] = strip[..., 3:4] / 255 * np.array([200, 30, 30]) + (1 - strip[..., 3:4] / 255) * 230
    strip[..., 3] = 255
    pad = np.full((strip.shape[0], sheet.shape[1] - strip.shape[1], 4), 255, np.float32)
    sheet = np.concatenate([sheet, np.concatenate([strip, pad], 1)], 0)
    png.write(out, np.clip(sheet, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    preview(sys.argv[2])
