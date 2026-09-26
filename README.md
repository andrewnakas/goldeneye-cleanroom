# GoldenEye 007 — clean room web build

Play: **https://andrewnakas.github.io/goldeneye-cleanroom/**

GoldenEye 007 built from the [n64decomp/007](https://github.com/n64decomp/007) decompilation, with
**every asset the decomp extracts from a ROM regenerated**, running in the browser on
[N64Wasm](https://github.com/nbarkhina/N64Wasm) (MIT). No original pixels or samples are included.

Controls: arrow keys = stick · **A** = Z (fire) · **D** = A · **S** = B · **Q/E** = L/R (aim) ·
**Enter** = Start · **I J K L** = C buttons · gamepads work too (remap under the `` ` `` menu).

## What is kept, what is generated

| Asset | Kept fact | Generated |
|---|---|---|
| Image bank textures (2,698) | format, size, mip levels, palette size, 4×4 colour grid (16×16 when ≥128 px), 2-bit alpha outline | colour from the grid + our own detail noise, our palettes, re-encoded with the game's lookup / zlib formats |
| Menu & HUD fonts (BankGothic, ZurichBold: 188 glyphs) | cell sizes, baselines, kerning classes | drawn with the project's original stroke font |
| Japanese / multibyte glyph banks | array sizes | box glyphs (unused by the US game) |
| Rare logo surface textures | 4×4 colour grid | grid + detail, box-filtered mips |
| Gun-barrel picture (folder menus) | size | drawn procedurally (`drawn.py`) |
| Instrument & sound-effect samples (292 waves) | length, loops, codebook size, coarse spectral outline, level, median pitch | resynthesised, our own VADPCM codebooks; bank sizes unchanged |
| Music | note sequences (melodies) | played by the resynthesised instruments |
| Code, level/model geometry, setups, text, attract demos | as in the decomp | — |

`games/goldeneye/taint.py` compares every generated texture (compressed and decoded), glyph, picture and
sample against the retail extraction for shared byte runs of 32 bytes or more: **0 failing**.

## Build (Windows, Git Bash)

Needs Python 3 + numpy/scipy, GNU make, Zig (host C), an LLVM release, mips64-elf binutils and the
recompiled IDO 5.3 passes (`tools/idowin/ido_cc.py` drives them; `cc` is wrapped by `build/build.sh`).

```sh
# dirty room, once (your own ROM; never published)
git clone -c core.autocrlf=false -c core.eol=lf https://github.com/n64decomp/007 dirty
cp baserom.u.z64 dirty/ && (cd dirty && bash scripts/extract_baserom.u.sh && make convert_props convert_chrs convert_guns)
games/goldeneye/build/build.sh dirty                                  # round trip: sha1 matches retail
python -m games.goldeneye.dump_textures dirty tex2raw.exe tex_raw.bin  # tools/tex2raw (decomp's own reader)
python -m games.goldeneye.extract_spec textures dirty tex_raw.bin      # -> spec/textures.json
python -m games.goldeneye.audio extract dirty                          # -> spec/audio.json
python -m games.goldeneye.srcpics extract pristine                     # -> spec/srcpics.json

# clean room
python -m games.goldeneye.generate all pristine dirty clean   # kept facts + textures
python -m games.goldeneye.audio build dirty clean
python -m games.goldeneye.fonts pristine clean
python -m games.goldeneye.srcpics build pristine clean
games/goldeneye/build/build.sh clean                           # -> clean/build/u/ge007.u.z64
python ports/emu/make_site.py site clean/build/u/ge007.u.z64
```

See `STATUS.md` for decisions and what's next.
