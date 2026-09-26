"""Clean room: spec/ + our code -> a decomp tree with regenerated assets.

    python -m games.goldeneye.generate setup <pristine> <dirty> <clean>   # tree + kept facts
    python -m games.goldeneye.generate textures <clean> [--only N,M]      # image bank
    python -m games.goldeneye.generate all <pristine> <dirty> <clean>

Kept facts copied from the dirty extraction (user scope: code, geometry, text, note data, demo
inputs): level/model geometry (bg .bin, chr/gun/prop Model.c from the decomp's own converters),
setups, text banks, music note sequences, attract-mode demo inputs, RSP boot microcode.
Everything else the decomp extracts is generated here.
"""
import json
import os
import re
import shutil
import sys

import numpy as np

from cleanroom.decomp.gen import from_digest, h32
from games.goldeneye import texcodec

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")

KEPT = [
    r"assets/obseg/bg/.*\.bin",
    r"assets/obseg/(chr|gun|prop)/[^/]+/Model\.c",
    r"assets/obseg/text/u/.*\.bin",
    r"assets/obseg/ob__ob_end\.seg",
    r"assets/ramrom/.*\.bin",
    r"assets/music/M[^/]*\.bin",
    r"bin/.*\.bin",
]
TOOLS = ["tools/gzipsrc/gzip", "tools/gzipsrc/gzip.exe", "tools/n64cksum", "tools/n64cksum.exe",
         "tools/armips", "tools/armips.exe"]


def setup(pristine, dirty, clean):
    if not os.path.isdir(clean):
        shutil.copytree(pristine, clean, ignore=shutil.ignore_patterns(".git"))
    pats = [re.compile(p) for p in KEPT]
    n = 0
    for root, _, files in os.walk(dirty):
        rel_root = os.path.relpath(root, dirty).replace("\\", "/")
        if rel_root.startswith(("build", ".git", "tools")):
            continue
        for f in files:
            rel = (rel_root + "/" + f).lstrip("./")
            if any(p.fullmatch(rel) for p in pats):
                dst = os.path.join(clean, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(dirty, rel), dst)
                n += 1
    for t in TOOLS:
        if os.path.exists(os.path.join(dirty, t)):
            shutil.copy2(os.path.join(dirty, t), os.path.join(clean, t))
    print(f"setup: {n} kept files -> {clean}")


# ------------------------------------------------------------------ textures

MAX_COMP = 3900          # texLoad's stack buffer is 4000 bytes (+ alignment slack)


def downscale(rgba, w, h):
    """Box-filter level 0 down to a smaller level's size."""
    H, W = rgba.shape[:2]
    ys = (np.arange(h + 1) * H // h)
    xs = (np.arange(w + 1) * W // w)
    out = np.zeros((h, w, 4), np.float32)
    f = rgba.astype(np.float32)
    for y in range(h):
        for x in range(w):
            out[y, x] = f[ys[y]:max(ys[y + 1], ys[y] + 1), xs[x]:max(xs[x + 1], xs[x] + 1)].reshape(-1, 4).mean(0)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def quantize(rgba, k, seed=0):
    """At most k colours (k-means on RGBA, deterministic). Returns (palette Nx4, index HxW)."""
    px = rgba.reshape(-1, 4).astype(np.float32)
    uniq, inv = np.unique(px, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    if len(uniq) <= k:
        return uniq.astype(np.uint8), inv.reshape(rgba.shape[:2])
    rng = np.random.default_rng(seed)
    cent = uniq[rng.choice(len(uniq), k, replace=False)]
    for _ in range(12):
        d = ((px[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                cent[j] = px[m].mean(0)
    d = ((px[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
    lab = d.argmin(1)
    return np.clip(cent + 0.5, 0, 255).astype(np.uint8), lab.reshape(rgba.shape[:2])


def pal16(pal, ia):
    """Palette RGBA -> u16 entries (IA16 for IA CI formats, RGBA5551 otherwise)."""
    out = []
    for r, g, b, a in pal.astype(np.int32):
        if ia:
            i = (r * 299 + g * 587 + b * 114) // 1000
            out.append((i << 8) | a)
        else:
            out.append(((r >> 3) << 11) | ((g >> 3) << 6) | ((b >> 3) << 1) | (1 if a >= 128 else 0))
    return out


def posterize(rgba, fmt, step):
    """Fewer distinct colours for the lookup encoder when a texture comes out too big."""
    q = rgba.astype(np.int32)
    q[..., :3] = (q[..., :3] // step) * step + step // 2
    return np.clip(q, 0, 255).astype(np.uint8)


def level0_image(t):
    fmt, w, h = t["levels"][0]
    d = {"w": w, "h": h, "grid": t.get("grid", [[128, 128, 128, 255]] * 16)}
    if "alpha2" in t:
        d["alpha2"] = t["alpha2"]
    return from_digest("ge/tex/" + t["name"], d)


def encode_texture(t, img0):
    """Encode our level-0 picture with the retail header/levels/formats."""
    levels = [list(l) for l in t["levels"]]
    hdr = t["header"]
    if hdr & 0x80 and not hdr & 0x40:
        # explicit levels: the header's count must match what we emit (header-only facts carry 1)
        while len(levels) < (hdr & 0x3f):
            f, w, h = levels[-1]
            levels.append([f, (w + 1) // 2, (h + 1) // 2])
    imgs = [img0] + [downscale(img0, w, h) for _, w, h in levels[1:]]
    if t.get("palette"):
        fmt = levels[0][0]
        kmax = 16 if fmt in (10, 12) else 256
        k = max(2, min(t["palette"], kmax))
        pal, idx0 = quantize(img0, k, h32("pal", t["name"]))
        # our own palette order (a sorted grey ramp would equal any other sorted ramp byte for byte)
        perm = np.random.default_rng(h32("order", t["name"])).permutation(len(pal))
        inv = np.empty_like(perm)
        inv[perm] = np.arange(len(perm))
        pal, idx0 = pal[perm], inv[idx0]
        pal_u16 = pal16(pal, fmt in (11, 12))
        idxs = [idx0]
        for im in imgs[1:]:
            d = ((im.reshape(-1, 1, 4).astype(np.int32) - pal[None].astype(np.int32)) ** 2).sum(-1)
            idxs.append(d.argmin(1).reshape(im.shape[:2]))
        return texcodec.encode_zlib(hdr, fmt, pal_u16, idxs)
    for step in (1, 8, 16, 32, 64):
        lv = [(f, posterize(im, f, step) if step > 1 else im) for (f, _, _), im in zip(levels, imgs)]
        data = texcodec.encode_nonzlib(hdr, lv)
        if len(data) <= min(MAX_COMP, max(t["size"], 1200)):
            return data
    return data


_ROLES = None


def default_override(t, k=None, tree=None):
    """Our drawn/typeset pictures for textures that need more than a colour grid."""
    global _ROLES
    from games.goldeneye import faces, labels, level_render, pictures
    img = level_render.override(t, tree) if tree is not None else None
    if img is None:
        img = pictures.override(t, None)
    if img is None and k is not None:
        img = labels.override(t, k)
    if img is None and k is not None and tree is not None:
        if _ROLES is None:
            _ROLES = faces.head_roles(tree)
        img = faces.override(t, k, _ROLES)
    return img


def textures(clean, only=None, overrides=None):
    T = json.load(open(os.path.join(SPEC, "textures.json")))
    split = os.path.join(clean, "assets/images/split")
    os.makedirs(split, exist_ok=True)
    sizes, big, total = [], 0, 0
    for k, t in enumerate(T):
        if only and k not in only:
            continue
        img0 = overrides(t) if overrides else default_override(t, k, clean)
        if img0 is not None:
            img0 = np.clip(np.asarray(img0, np.float32) + 0.5, 0, 255).astype(np.uint8)
        if img0 is None:
            img0 = level0_image(t)
        data = encode_texture(t, img0)
        if len(data) > MAX_COMP:
            big += 1
        open(os.path.join(split, t["name"] + ".bin"), "wb").write(data)
        sizes.append((t["name"], len(data)))
        total += len(data)
    if not only:
        write_image_tables(clean, [s for _, s in sizes])
    print(f"textures: {len(sizes)} written, {total} bytes, {big} over {MAX_COMP}")


def write_image_tables(clean, sizes):
    """images.def sizes + imagelist.u.csv offsets for the regenerated bank."""
    p = os.path.join(clean, "assets/images.def")
    lines, k = [], 0
    for line in open(p):
        m = re.match(r"(\s*IMAGE\([^,]+,\s*)(0x[0-9A-Fa-f]+|\d+)(.*)", line, re.S)
        if m:
            line = m.group(1) + "0x%X" % sizes[k] + m.group(3)
            k += 1
        lines.append(line)
    open(p, "w", newline="\n").write("".join(lines))
    c = os.path.join(clean, "imagelist.u.csv")
    rows = [l.rstrip("\n").split(",") for l in open(c) if l.strip()]
    off = int(rows[0][0])
    out = []
    for r, s in zip(rows, sizes):
        r[0], r[1] = str(off), str(s)
        off += s
        out.append(",".join(r))
    open(c, "w", newline="\n").write("\n".join(out) + "\n")
    comb = os.path.join(clean, "assets/images/combined/combined.bin")
    if os.path.exists(comb):
        os.remove(comb)


def main(argv):
    cmd = argv[0]
    if cmd == "setup":
        setup(*argv[1:4])
    elif cmd == "textures":
        only = None
        if "--only" in argv:
            only = {int(x) for x in argv[argv.index("--only") + 1].split(",")}
        textures(argv[1], only)
    elif cmd == "all":
        pristine, dirty, clean = argv[1:4]
        setup(pristine, dirty, clean)
        textures(clean)
        pictures(clean)
        from games.goldeneye import audio, fonts, srcpics
        audio.build(dirty, clean)
        fonts.main([pristine, clean])
        srcpics.build(pristine, clean)
    elif cmd == "pictures":
        pictures(argv[1])


def pictures(clean):
    from games.goldeneye import drawn
    open(os.path.join(clean, "assets/ge007.u.2A4D50.usedby7F008DE4.bin"), "wb").write(drawn.rle8(drawn.gunbarrel()))
    print("pictures: gun barrel")


if __name__ == "__main__":
    main(sys.argv[1:])
