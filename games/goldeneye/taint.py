"""Taint report: every generated asset vs every retail one; shared runs >= 32 bytes fail.

    python -m games.goldeneye.taint <dirty tree> <clean tree> <tex2raw.exe> <retail tex_raw.bin>

Scanned (clean vs retail, in the same representation):
  image bank: decoded native pixels of every level, and the compressed files
  sound banks: .tbl bytes and decoded PCM
  fonts (glyph bytes), Rare logo pixels, gun-barrel picture (compressed and expanded),
  textures embedded in prop models (legal page, GoldenEye/Nintendo logos)
Kept facts (geometry, setups, text, note sequences, demo inputs, bank structure) are not scanned.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np

from cleanroom import taint
from cleanroom.audio import vadpcm
from games.goldeneye import audio, texcodec
from games.goldeneye.fonts import parse_u32_arrays


def tex_streams(raw_path):
    for k, r in enumerate(texcodec.read_raw_dump(raw_path)):
        for j, lv in enumerate(r["levels"]):
            yield f"tex{k}.{j}", lv["raw"]


def pcm_streams(tree, spec):
    for name in audio.BANKS:
        ctl = open(os.path.join(tree, f"assets/music/{name}.ctl"), "rb").read()
        tbl = open(os.path.join(tree, f"assets/music/{name}.tbl"), "rb").read()
        yield f"{name}.tbl", tbl
        for wt, w in audio.waves_of(ctl).items():
            d = tbl[w["base"]:w["base"] + w["len"]]
            if w["type"] == 0 and w["book_off"]:
                pcm = vadpcm.decode(d, audio.book_at(ctl, w["book_off"]))
                yield f"{name}.pcm{wt}", np.asarray(pcm, ">i2").tobytes()


def src_streams(tree):
    for f, pre in (("assets/font/fontBankGothic.c", "fontBankGothic"), ("assets/font/fontZurichBold.c", "fontZurichBold")):
        a = parse_u32_arrays(open(os.path.join(tree, f)).read())
        yield f, np.asarray(a[pre + "_fontbytes"], ">u4").tobytes()
    a = parse_u32_arrays(open(os.path.join(tree, "assets/rarewarelogo.c")).read())
    for n, v in a.items():
        if n.startswith("img"):
            yield "logo." + n, np.asarray(v, ">u4").tobytes()
    for f in ("assets/font_chardataj.c", "assets/font_chardatae.c"):
        a = parse_u32_arrays(open(os.path.join(tree, f)).read())
        yield f, b"".join(np.asarray(v, ">u4").tobytes() for v in a.values())
    from games.goldeneye import embedded
    yield from embedded.streams(tree)
    b = open(os.path.join(tree, "assets/ge007.u.2A4D50.usedby7F008DE4.bin"), "rb").read()
    yield "gunbarrel.rle", b
    out, p = bytearray(), 10
    w, h = int.from_bytes(b[0:2], "big"), int.from_bytes(b[2:4], "big")
    while len(out) < w * h and p + 1 < len(b):
        out += bytes([b[p + 1]]) * b[p]
        p += 2
    yield "gunbarrel.pixels", bytes(out)


def main():
    dirty, clean, exe, retail_raw = sys.argv[1:5]
    tmp = tempfile.mkdtemp(prefix="ge_taint_")
    clean_raw = os.path.join(tmp, "clean_raw.bin")
    names = [l.split(",")[2] for l in open(os.path.join(dirty, "build/u/imagelist.csv")) if l.strip()]
    from games.goldeneye.dump_textures import dump
    dump(dirty, clean, exe, clean_raw)

    def files(tree):
        for n in names:
            yield "file:" + n, open(os.path.join(tree, n), "rb").read()

    retail = [s for _, s in tex_streams(retail_raw)] + [s for _, s in files(dirty)] + \
             [s for _, s in pcm_streams(dirty, None)] + [s for _, s in src_streams(dirty)]
    index = taint.build_index(retail)
    ours = list(tex_streams(clean_raw)) + list(files(clean)) + list(pcm_streams(clean, None)) + list(src_streams(clean))
    hits = taint.scan(index, ours)
    fail = [h for h in hits if h[3] >= taint.FAIL_RUN]
    print(f"taint: {len(ours)} generated streams scanned, {len(hits)} with shared windows, {len(fail)} failing")
    for h in sorted(fail, key=lambda h: -h[3])[:10]:
        print("  FAIL", h)
    for h in sorted(hits, key=lambda h: -h[3])[:3]:
        print("  worst", h)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
