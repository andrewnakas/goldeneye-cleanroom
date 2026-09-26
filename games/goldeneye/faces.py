"""In-game head textures: the kept colour grid (where skin, hair and collar are) + facial features
drawn by us at the head textures' common layout (32x64 strips: one front, two sides per head).

Front: eyes (whites, iris, lid line), brows, nose shading, nostrils, mouth, chin shadow.
Side: an ear and a jaw shadow. Colours for features come from the grid (skin/hair tones).
Which textures are heads comes from the decomp's head models (chr/head*/Model.c image lists);
the front is the most left-right symmetric strip of each head.
"""
import os
import re

import numpy as np

from cleanroom.decomp.gen import detail, h32, upsample_grid

HERE = os.path.dirname(os.path.abspath(__file__))
_HEADS = None


def head_roles(tree):
    """{texture index: 'front'|'side'} from the head models' texture lists."""
    import json
    T = json.load(open(os.path.join(HERE, "spec", "textures.json")))
    names = {t["name"]: k for k, t in enumerate(T)}
    roles = {}
    chr_dir = os.path.join(tree, "assets/obseg/chr")
    for d in sorted(os.listdir(chr_dir)):
        if not d.startswith("head"):
            continue
        src = open(os.path.join(chr_dir, d, "Model.c")).read()
        ids = []
        for n in re.findall(r"IMAGE_([A-Za-z0-9_]+)", src):
            k = names.get(n)
            if k is not None and k not in ids and T[k]["levels"][0][1:] == [32, 64] and "grid" in T[k]:
                ids.append(k)
        if not ids:
            continue
        sym = [symmetry(T[k]["grid"]) for k in ids]
        front = ids[int(np.argmin(sym))]
        for k in ids:
            roles.setdefault(k, "front" if k == front else "side")
    return roles


def symmetry(grid):
    g = np.asarray(grid, np.float32).reshape(4, 4, 4)[..., :3]
    return float(np.abs(g - g[:, ::-1]).mean())


def _ell(xx, yy, cx, cy, rx, ry):
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2


def paint(t, role):
    """Upright RGBA picture (the caller flips to storage order)."""
    f, w, h = t["levels"][0]
    g = np.asarray(t["grid"], np.float32).reshape(4, 4, 4)
    # grid is in storage order (bottom row first): flip to upright
    g = g[::-1]
    S = 4
    W, H = w * S, h * S
    img = upsample_grid(g.reshape(-1, 4).tolist(), 4, W, H)
    img[..., :3] *= detail(h32("face", t["name"]), W, H, 0.04, 3.0 * S)[..., None]
    skin = g[1:3, 1:3, :3].reshape(-1, 3).mean(0)
    hair = g[0, :, :3].mean(0)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xx, yy = (xx + 0.5) / W, (yy + 0.5) / H

    def put(mask, colour, amount=1.0):
        m = np.clip(mask, 0, 1)[..., None] * amount
        img[..., :3] = img[..., :3] * (1 - m) + np.asarray(colour, np.float32) * m

    def soft(d, edge=0.25):
        return np.clip((1 - d) / edge, 0, 1)

    dark = np.minimum(hair, skin * 0.45)
    if role == "front":
        ey = 0.38
        for ex in (0.30, 0.70):
            put(soft(_ell(xx, yy, ex, ey + 0.012, 0.15, 0.035)), skin * 0.72, 0.6)       # socket shade
            put(soft(_ell(xx, yy, ex, ey, 0.115, 0.022), 0.4), [235, 230, 225])              # white
            put(soft(_ell(xx, yy, ex, ey, 0.055, 0.021), 0.3), [70, 55, 45])                 # iris
            put(soft(_ell(xx, yy, ex, ey, 0.025, 0.012), 0.3), [15, 10, 10])                 # pupil
            put(soft(_ell(xx, yy, ex, ey - 0.018, 0.12, 0.007), 0.5), dark, 0.9)            # lid line
            put(soft(_ell(xx, yy, ex, ey - 0.052, 0.14, 0.010), 0.5), hair * 0.7, 0.9)      # brow
        put(soft(_ell(xx, yy, 0.56, 0.47, 0.035, 0.075), 0.6), skin * 0.8, 0.7)             # nose side shade
        put(soft(_ell(xx, yy, 0.5, 0.515, 0.12, 0.016), 0.5), skin * 0.7, 0.6)               # nose base
        for nx in (0.44, 0.56):
            put(soft(_ell(xx, yy, nx, 0.515, 0.03, 0.008), 0.5), skin * 0.4, 0.9)             # nostrils
        put(soft(_ell(xx, yy, 0.5, 0.585, 0.19, 0.013), 0.5), skin * np.array([0.72, 0.5, 0.5]), 1.0)  # lips
        put(soft(_ell(xx, yy, 0.5, 0.583, 0.18, 0.004), 0.5), skin * 0.35, 1.0)              # mouth line
        put(soft(_ell(xx, yy, 0.5, 0.66, 0.25, 0.02), 0.8), skin * 0.8, 0.5)                 # chin shadow
    else:
        put(soft(_ell(xx, yy, 0.5, 0.43, 0.13, 0.075), 0.3), skin * 0.85)                    # ear
        put(soft(_ell(xx, yy, 0.5, 0.43, 0.06, 0.04), 0.5), skin * 0.55, 0.8)                # ear hole
        put(soft(_ell(xx, yy, 0.5, 0.66, 0.5, 0.03), 0.8), skin * 0.8, 0.4)                  # jaw
    out = img.reshape(h, S, w, S, 4).mean((1, 3))
    out[..., 3] = 255
    return np.clip(out, 0, 255)


def override(t, k, roles):
    role = roles.get(k)
    if role is None:
        return None
    return np.ascontiguousarray(paint(t, role)[::-1])
