# GoldenEye 007 clean room: status

Live: **https://andrewnakas.github.io/goldeneye-cleanroom/** (repo andrewnakas/goldeneye-cleanroom; site on gh-pages,
published by `games/goldeneye/publish.sh`, which refuses to publish unless the taint scan passes).

## Decisions (log)
- 2026-09-25 22:42: ROM `GoldenEye 007 (USA).z64` sha1 abe01e4a… = decomp's US target. Decomp n64decomp/007 cloned
  (depth 1, LF) to `D:/n64work/goldeneye/pristine`; dirty tree `D:/n64work/goldeneye/dirty` (baserom + extracted assets).
- **Web route = clean ROM + N64Wasm** (playbook §4 option 3). Why: GoldenEye has no PC port (the decomp still
  has large asm parts), so no Emscripten target; N64Wasm (MIT, ParaLLEl core, prebuilt at
  `C:/Users/andre/n64work/n64wasm/dist`) is proven on SSB64 with keyboard + gamepad + audio; retail GE runs at 60 fps
  in headless Edge.
- **The decomp builds natively on Windows and matches retail** (sha1): `games/goldeneye/build/build.sh <tree>`
  (IDO passes via `tools/idowin/ido_cc.py` — gained `-Olimit`, `-o32` and piped-stdin support; mips64-elf binutils;
  decomp gzip built with zig + binary stdio; armips.exe from the SM64 tree; `cpp` shim; Python AI_PRINT converter
  because Git's sed mis-handles the decomp's regex). So the clean ROM is a real decomp build with regenerated assets;
  the linker re-lays everything (no packer).
- Build traps: the Makefile has no header deps and marks objects `.SECONDARY` -> `build.sh` deletes `image.o` when
  `images.def` changed (texture sizes -> offsets compiled into image.c) and always relinks. Stale image.o = blue screen.
- Kept facts (copied from the dirty extraction by `generate.py setup`): bg geometry .bin, chr/gun/prop Model.c
  (geometry, from the decomp's own converters), setups/briefings (C in the decomp), text banks, music note sequences,
  attract demo inputs, RSP boot microcode. Everything else is generated.
- Textures: GE image-bank format decoded by `tools/tex2raw` (the decomp's own libpdtex reader; fixed two lookup bugs
  vs GE's image.c; one process per file because the batch decoder crashes on state). Spec = header byte, levels
  (format/w/h), palette size, 4x4 grid (16x16 >= 128 px), 2-bit alpha. Encoder: LOOKUP method (non-zlib) or
  palette+deflate (zlib/CI), k-means palettes in a seeded order (sorted grey ramps coincided with retail byte runs).
  Every texture must stay under the 4000-byte `texLoad` stack buffer (all do).
- Audio: 292 waves of instruments/sfx banks resynthesised from outlines; own VADPCM books; .ctl/.tbl sizes unchanged.
- Fonts (BankGothic menus, ZurichBold dossier/HUD): glyphs drawn with our stroke font fitted to each cell; metrics
  and kerning kept. Font struct is packed: glyph offsets are relative to the end of kerning+char table (0xB74).
- Rare logo surface textures (`rarewarelogo.c`) regenerated from 4x4 grids; gun-barrel folder background (RLE blob
  `ge007.u.2A4D50…bin`, 440x299) drawn procedurally (`drawn.py`). Japanese glyph banks -> box glyphs (unused in US).
- Taint: `python -m games.goldeneye.taint` -> 0 failing of 7,526 streams (textures compressed + decoded, glyphs,
  logo, gun barrel, tbl + decoded PCM).

## Works (2026-09-26 00:45)
- Clean ROM boots: logos, legal screen, file select, mission select, dossier text readable (both fonts);
  Dam mission loads and plays (walking, PP7, ammo HUD) in headless N64Wasm.

## Known issues / next
- Pictures: Bond photo on the folders, mission-select thumbnails, MI6 crest (MI6_*), monitor screens, posters are
  colour grids -> draw/render them (c_render of Bond's head model for the photo; level renders for thumbnails).
- Faces: character head textures (head* models) are grids -> face briefs (facepaint).
- Text-bearing textures (SELECT FILE / COPY / ERASE icons, ammo box labels, signs, monitor text) -> re-typeset.
- Legal screen / Nintendo logo check; ':' glyph in ZurichBold looks blank.
- Voices: GE has almost no speech; guard vocal sfx are resynthesised noise. Practice pack still to build.
- Headless speed varies a lot with machine load (other sessions); a real browser should be 60 fps on menus.

## For the morning
1. Open the live link in a desktop browser (keyboard: arrows move, A fire, D use, Enter start; or a gamepad) and play
   Dam. Tell me what looks/sounds worst.
2. Nothing to record yet (voice practice pack pending).
