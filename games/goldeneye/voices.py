"""Guard/character vocal sounds (inside the sfx bank): placeholders + practice pack.

    python -m games.goldeneye.voices find <dirty>            dirty room: which sfx waves are voices,
                                                             and the words heard -> voice_lines.json
    python -m games.goldeneye.voices build                   Piper TTS placeholders -> overrides/sounds/sfx/<wave>.wav
    python -m games.goldeneye.voices practice <dirty> <out>  PERSONAL practice pack (outside the repo, never published)

voice_lines.json keeps only facts: the slot, its length, the median pitch and the words (or the
kind of vocal sound). The placeholders are spoken by Piper character voices (no cloning); the
user's own recordings can replace them later (same file names in overrides/sounds/sfx/).
"""
import json
import os
import struct
import sys
import wave

import numpy as np

from cleanroom.audio import vadpcm
from games.goldeneye import audio

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = os.path.join(HERE, "voice_lines.json")
OVR = os.path.join(HERE, "overrides", "sounds", "sfx")
PIPER = "C:/Users/andre/n64work/piper_voices"
RATE = 22050
VOICES = {"male": ("en_US-ryan-high", 1.0), "male2": ("en_US-joe-medium", 1.0),
          "female": ("en_US-amy-medium", 1.0)}


def _retail_waves(dirty):
    ctl = open(os.path.join(dirty, "assets/music/sfx.ctl"), "rb").read()
    tbl = open(os.path.join(dirty, "assets/music/sfx.tbl"), "rb").read()
    for wt, w in sorted(audio.waves_of(ctl).items()):
        if w["type"] != 0 or not w["book_off"]:
            continue
        pcm = vadpcm.decode(tbl[w["base"]:w["base"] + w["len"]], audio.book_at(ctl, w["book_off"]))
        yield wt, w, np.asarray(pcm, np.float32) / 32768


def find(dirty):
    from faster_whisper import WhisperModel
    from cleanroom.audio.pitch import median_f0
    spec = json.load(open(audio.SPEC))["sfx"]["waves"]
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    out = {}
    for wt, w, x in _retail_waves(dirty):
        dur = len(x) / RATE
        if not 0.15 <= dur <= 4.0 or spec[str(wt)]["loop"]:
            continue
        f0 = median_f0(x, RATE)
        if not f0 or not 75 <= f0 <= 600:
            continue
        pad = np.concatenate([np.zeros(RATE // 4, np.float32), x, np.zeros(RATE // 4, np.float32)])
        import librosa
        y = librosa.resample(pad, orig_sr=RATE, target_sr=16000)
        segs, info = model.transcribe(y, language="en", beam_size=5, vad_filter=False)
        segs = list(segs)
        text = " ".join(s.text.strip() for s in segs).strip()
        nsp = min((s.no_speech_prob for s in segs), default=1.0)
        if not text or nsp > 0.6:
            continue
        out[str(wt)] = {"text": text, "dur": round(dur, 2), "f0": round(float(f0)), "who": "female" if f0 > 220 else "male",
                        "no_speech": round(float(nsp), 2)}
    json.dump({"_doc": "sfx waves that are voices (dirty-room finding): words heard, length, median pitch",
               **out}, open(LINES, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"voices: {len(out)} vocal sfx slots -> {LINES}")


def _speak(who, text, length_scale):
    from piper import PiperVoice, SynthesisConfig
    v = PiperVoice.load(os.path.join(PIPER, VOICES[who][0] + ".onnx"))
    cfg = SynthesisConfig(length_scale=length_scale, noise_scale=0.6, noise_w_scale=0.7)
    x = np.concatenate([c.audio_float_array for c in v.synthesize(text, syn_config=cfg)]).astype(np.float32)
    return x, v.config.sample_rate


def build():
    import librosa
    L = {k: v for k, v in json.load(open(LINES, encoding="utf-8")).items() if not k.startswith("_")}
    os.makedirs(OVR, exist_ok=True)
    for wt, v in L.items():
        best = None
        for ls in (1.0, 0.85, 0.7, 0.55):
            x, sr = _speak(v["who"], v["text"], ls)
            x = librosa.resample(x, orig_sr=sr, target_sr=RATE)
            nz = np.nonzero(np.abs(x) > 0.01)[0]
            x = x[nz[0]:nz[-1] + 1] if len(nz) else x
            best = x
            if len(x) / RATE <= v["dur"]:
                break
        n = int(v["dur"] * RATE)
        y = np.zeros(n, np.float32)
        y[:min(n, len(best))] = best[:n]
        with wave.open(os.path.join(OVR, f"{wt}.wav"), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(RATE)
            f.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    print(f"voices: {len(L)} placeholders -> {OVR}")


def practice(dirty, out):
    L = {k: v for k, v in json.load(open(LINES, encoding="utf-8")).items() if not k.startswith("_")}
    os.makedirs(os.path.join(out, "clips"), exist_ok=True)
    beep = (0.2 * np.sin(2 * np.pi * 880 * np.arange(int(0.08 * RATE)) / RATE)).astype(np.float32)

    def wr(p, x):
        with wave.open(p, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(RATE)
            f.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())

    tracks, script = {}, ["GoldenEye vocal sounds: record 2-3 takes each, in character, after each beep.",
                          "Save your takes as overrides/sounds/sfx/<slot>.wav (mono, any rate) and rebuild.", ""]
    waves = {str(wt): x for wt, w, x in _retail_waves(dirty)}
    for i, (wt, v) in enumerate(sorted(L.items(), key=lambda kv: (kv[1]["who"], int(kv[0]))), 1):
        x = waves[wt]
        wr(os.path.join(out, "clips", f"{i:02d}_slot{wt}.wav"), x)
        gap = np.zeros(int((len(x) / RATE * 1.5 + 1.5) * RATE), np.float32)
        tracks.setdefault(v["who"], []).extend([x, np.zeros(int(0.3 * RATE), np.float32), beep, gap])
        script.append(f"{i:02d}  {v['who']:7s} slot {wt:>6s}  max {v['dur']:.2f}s  \"{v['text']}\"")
    for who, parts in tracks.items():
        wr(os.path.join(out, f"practice_{who}_call_and_response.wav"), np.concatenate(parts))
    script += ["", "These reference clips come from your own ROM: practice only, never share or commit them."]
    open(os.path.join(out, "SCRIPT.txt"), "w", encoding="utf-8").write("\n".join(script))
    print(f"practice pack: {len(L)} clips, tracks {sorted(tracks)} -> {out}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "find":
        find(sys.argv[2])
    elif cmd == "build":
        build()
    else:
        practice(sys.argv[2], sys.argv[3])
