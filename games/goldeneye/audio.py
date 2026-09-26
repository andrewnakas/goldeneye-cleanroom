"""Sound banks (instruments/sfx .ctl + .tbl): dirty facts -> resynthesised clean samples.

    python -m games.goldeneye.audio extract <dirty tree>   -> spec/audio.json (facts only)
    python -m games.goldeneye.audio build <dirty tree> <clean tree>

Kept per wave: byte length (every sample keeps its frame count), loop start/end/count, the
codebook's predictor count (so the .ctl keeps its size), a coarse spectral outline
(cleanroom.audio.descriptor), the RMS level and the median pitch. Bank structure (envelopes,
keymaps, pans) stays as the game's data. Generated: every waveform, our own VADPCM codebooks and
loop states. The .tbl is rebuilt from zeros, so no retail sample byte survives.
Music sequences (M*.bin note data) are kept as the user-approved melodies.
"""
import json
import os
import struct
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from cleanroom.audio import descriptor, vadpcm
from cleanroom.audio.pitch import median_f0

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec", "audio.json")
OVR = os.path.join(HERE, "overrides", "sounds")
RATE = 22050          # nominal: only used to express the outline; synthesis uses the same rate
BANKS = ["instruments", "sfx"]


def waves_of(ctl):
    """{wave_off: dict(base, len, type, loop_off, book_off)} reachable from the bank file."""
    out = {}
    rev, n = struct.unpack_from(">hh", ctl, 0)
    for bo in struct.unpack_from(">%dI" % n, ctl, 4):
        if not bo:
            continue
        cnt, fl, pad, rate, perc = struct.unpack_from(">hBBiI", ctl, bo)
        insts = [i for i in struct.unpack_from(">%dI" % cnt, ctl, bo + 12) if i] + ([perc] if perc else [])
        for io in insts:
            ns = struct.unpack_from(">h", ctl, io + 14)[0]
            for so in struct.unpack_from(">%dI" % ns, ctl, io + 16):
                if not so:
                    continue
                wt = struct.unpack_from(">I", ctl, so + 8)[0]
                base, ln, typ, wfl, lp, bk = struct.unpack_from(">IiBBxxII", ctl, wt)
                out[wt] = dict(base=base, len=ln, type=typ, loop_off=lp, book_off=bk)
    return out


def book_at(ctl, off):
    order, npred = struct.unpack_from(">ii", ctl, off)
    return {"order": order, "npred": npred,
            "book": list(struct.unpack_from(">%dh" % (order * npred * 8), ctl, off + 8))}


def _describe(args):
    key, data, book, typ = args
    if typ == 0:
        pcm = vadpcm.decode(data, book)
    else:
        pcm = np.frombuffer(data[:len(data) // 2 * 2], ">i2").astype(np.int64)
    d = descriptor.describe(pcm, RATE)
    f0 = median_f0(pcm.astype(np.float32) / 32768.0, RATE) if len(pcm) > 2048 else None
    return key, d, f0, int(np.sqrt(np.mean(pcm.astype(np.float64) ** 2))) if len(pcm) else 0


def extract(dirty):
    spec, jobs = {}, []
    for name in BANKS:
        ctl = open(os.path.join(dirty, f"assets/music/{name}.ctl"), "rb").read()
        tbl = open(os.path.join(dirty, f"assets/music/{name}.tbl"), "rb").read()
        ws = waves_of(ctl)
        spec[name] = {"tbl_len": len(tbl), "waves": {}}
        for wt, w in sorted(ws.items()):
            bk = book_at(ctl, w["book_off"]) if w["type"] == 0 and w["book_off"] else {"order": 0, "npred": 0}
            loop = None
            if w["loop_off"]:
                s, e, c = struct.unpack_from(">III", ctl, w["loop_off"])
                loop = [s, e, c]
            spec[name]["waves"][str(wt)] = dict(base=w["base"], len=w["len"], type=w["type"],
                                                 npred=bk["npred"], order=bk["order"], loop=loop,
                                                 book_off=w["book_off"], loop_off=w["loop_off"])
            jobs.append(((name, str(wt)), tbl[w["base"]:w["base"] + w["len"]], bk, w["type"]))
    with ProcessPoolExecutor(8) as ex:
        for (name, wt), d, f0, rms in ex.map(_describe, jobs, chunksize=4):
            spec[name]["waves"][wt].update(desc=d, f0=f0, rms=rms)
    json.dump(spec, open(SPEC, "w"))
    n = sum(len(v["waves"]) for v in spec.values())
    lp = sum(1 for v in spec.values() for w in v["waves"].values() if w["loop"])
    print(f"audio: {n} waves ({lp} looped) -> {SPEC}")


def _make(args):
    name, wt, w = args
    adpcm = w["type"] == 0
    nsamp = w["len"] // 9 * 16 if adpcm else w["len"] // 2
    ovr = os.path.join(OVR, name, f"{wt}.wav")
    if os.path.exists(ovr):
        import scipy.io.wavfile as wavfile
        sr, x = wavfile.read(ovr)
        x = x.astype(np.float32) / (32768.0 if x.dtype == np.int16 else 1.0)
        if x.ndim > 1:
            x = x.mean(1)
        x = np.interp(np.linspace(0, len(x) - 1, nsamp), np.arange(len(x)), x) if len(x) != nsamp else x
    else:
        x = descriptor.synthesize(w["desc"], nsamp, RATE, seed=int(wt) * 7 + len(name))
    if w["loop"] and w["loop"][2]:
        s, e = w["loop"][0], min(w["loop"][1], nsamp)
        if e - s > 64:
            x = descriptor.make_loop_seamless(np.asarray(x, np.float64), s, e)
    x = np.asarray(x, np.float64)
    peak = np.abs(x).max() + 1e-9
    target = max(w["rms"], 16) / 32768.0
    cur = np.sqrt(np.mean(x ** 2)) + 1e-9
    x = x * min(target / cur, 0.95 / peak)
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype(np.int64)
    if not adpcm:
        data = pcm.astype(">i2").tobytes()
        return name, wt, data[:w["len"]] + bytes(max(0, w["len"] - len(data))), None, None
    fam = vadpcm.PREDICTORS if w["npred"] >= 4 else [(1.0, 0.0), (1.9, -0.92)][:max(1, w["npred"])]
    book = vadpcm.make_book(fam)
    data, book, dec = vadpcm.encode(pcm, book)
    data = data[:w["len"]] + bytes(max(0, w["len"] - len(data)))
    state = vadpcm.loop_state(dec, w["loop"][0]) if w["loop"] else None
    return name, wt, data, book, state


def build(dirty, clean):
    spec = json.load(open(SPEC))
    jobs = [(name, wt, w) for name in spec for wt, w in spec[name]["waves"].items()]
    res = {}
    with ProcessPoolExecutor(8) as ex:
        for name, wt, data, book, state in ex.map(_make, jobs, chunksize=2):
            res[(name, wt)] = (data, book, state)
    for name in BANKS:
        # .ctl = bank structure (kept); books and loop states are replaced below
        ctl = bytearray(open(os.path.join(dirty, f"assets/music/{name}.ctl"), "rb").read())
        tbl = bytearray(spec[name]["tbl_len"])
        for wt, w in spec[name]["waves"].items():
            data, book, state = res[(name, wt)]
            tbl[w["base"]:w["base"] + w["len"]] = data
            if book is not None:
                assert len(book["book"]) == w["order"] * w["npred"] * 8, (name, wt, len(book["book"]))
                struct.pack_into(">%dh" % len(book["book"]), ctl, w["book_off"] + 8, *book["book"])
            if w["loop_off"]:
                st = state if state is not None else [0] * 16
                struct.pack_into(">16h", ctl, w["loop_off"] + 12, *[max(-32768, min(32767, int(v))) for v in st])
        open(os.path.join(clean, f"assets/music/{name}.ctl"), "wb").write(ctl)
        open(os.path.join(clean, f"assets/music/{name}.tbl"), "wb").write(tbl)
    print(f"audio: {len(jobs)} waves regenerated -> {clean}/assets/music")


if __name__ == "__main__":
    if sys.argv[1] == "extract":
        extract(sys.argv[2])
    else:
        build(sys.argv[2], sys.argv[3])
