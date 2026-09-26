"""Pixel arrays the decomp keeps in C source (retail pixels): the Rare logo surface textures.

    python -m games.goldeneye.srcpics extract <pristine>        -> spec/srcpics.json (grid facts)
    python -m games.goldeneye.srcpics build <pristine> <clean>

assets/rarewarelogo.c has four RGBA16 32x32 mip chains (imgRAre_*, img_raRE_*, ...). Kept: array
size and a 4x4 colour grid of level 0. Generated: all pixels (grid + our detail, box-filtered mips).
"""
import json
import os
import re
import sys

import numpy as np

from cleanroom.decomp.gen import from_digest
from cleanroom.decomp.spec import grid
from games.goldeneye.fonts import parse_u32_arrays
from games.goldeneye.generate import downscale

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec", "srcpics.json")
FILE = "assets/rarewarelogo.c"
PAT = re.compile(r"img\w+_0x[0-9A-Fa-f]+$")


def rgba16_to_rgba(words, w, h):
    b = np.frombuffer(np.asarray(words, ">u4").tobytes()[:w * h * 2], ">u2").astype(np.uint32)
    px = np.stack([(b >> 11) & 31, (b >> 6) & 31, (b >> 1) & 31], -1) * 255 // 31
    a = (b & 1) * 255
    return np.concatenate([px, a[:, None]], -1).reshape(h, w, 4).astype(np.uint8)


def extract(pristine):
    arr = parse_u32_arrays(open(os.path.join(pristine, FILE)).read())
    out = {}
    for name, words in arr.items():
        if PAT.match(name):
            img = rgba16_to_rgba(words, 32, 32)
            out[name] = {"words": len(words), "w": 32, "h": 32, "grid": grid(img, 4)}
    json.dump(out, open(SPEC, "w"), indent=0)
    print(f"srcpics: {len(out)} arrays -> {SPEC}")


def pack16(img):
    p = img.reshape(-1, 4).astype(np.uint32)
    return (((p[:, 0] >> 3) << 11) | ((p[:, 1] >> 3) << 6) | ((p[:, 2] >> 3) << 1) | (p[:, 3] >= 128)).astype(">u2").tobytes()


def build(pristine, clean):
    spec = json.load(open(SPEC))
    src = open(os.path.join(pristine, FILE)).read()
    for name, d in spec.items():
        img = from_digest("ge/srcpic/" + name, d)
        data, w = b"", 32
        while len(data) < d["words"] * 4 and w >= 1:
            data += pack16(img if w == 32 else downscale(img, w, w))
            w //= 2
        data = data[:d["words"] * 4].ljust(d["words"] * 4, b"\0")
        words = np.frombuffer(data, ">u4")
        body = ",\n".join("    " + ", ".join("0x%08X" % v for v in words[i:i + 8]) for i in range(0, len(words), 8))
        src = re.sub(r"(u32\s+" + name + r"\s*\[\s*\d*\s*\]\s*=\s*\{)(.*?)(\};)",
                     lambda m: m.group(1) + "\n" + body + "\n" + m.group(3), src, count=1, flags=re.S)
    open(os.path.join(clean, FILE), "w", newline="\n").write(src)
    print(f"srcpics: {len(spec)} arrays regenerated in {FILE}")


if __name__ == "__main__":
    extract(sys.argv[2]) if sys.argv[1] == "extract" else build(sys.argv[2], sys.argv[3])
