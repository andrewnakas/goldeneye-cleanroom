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

## Works (2026-09-26 ~02:00)
- Clean ROM boots: logos, legal screen, file select, mission select, dossier text readable (both fonts);
  Dam mission loads and plays (walking, PP7, ammo HUD) in headless N64Wasm.
- Menu pictures drawn from our briefs (`picture_briefs.json`, `pictures.py`): Bond/character portraits (generic
  B&W studio busts: costume + hair only, no likenesses), mission/MP recon thumbnails, CLASSIFIED/CONFIDENTIAL/
  EYES ONLY/FOR YOUR/OHMSS stamps re-typeset, a service crest. Verified upright in-game (GE stores textures
  bottom row first; pictures are painted upright, tiled, flipped).
- In-game heads (96 strips from the head models): kept skin/hair grid + our eyes/brows/nose/mouth (front) or ear (sides).
- Text inside textures re-typeset (`text_labels.json`, `labels.py`; Cyrillic added to the shared stroke font):
  Russian signs, ammo-box labels, PERSONNEL, KH-89, 715, monitor captions, Tazer Boy; 7-segment digits drawn.
- Texture encoder: lookup or Huffman-lookup (ported the game's tree builder; exact round trip), whichever is smaller.
- Voices: GE has only a handful of vocal sfx (6 found: grunts/screams); Piper placeholders in
  `overrides/sounds/sfx/`, practice pack at `D:/n64work/goldeneye/practice` (never published).

## Known issues / next
- Site hardening (02:10): the page's 9 CDN libraries are vendored (a slow CDN left the emulator hidden) and an
  IndexedDB/`myClass` startup race is guarded. Live site verified to boot to the legal screen (headless).
- Question for you: textures whose content is all alpha (legal-screen GOLDENEYE 007 logo, the two signatures,
  some icons) keep their exact silhouette through the kept 2-bit alpha outline (agreed scope, same as SM64).
  Say if you want those redrawn/re-typeset instead.
- Gameplay re-check of the latest builds is pending: this machine was at 60-70% CPU from other sessions and
  headless N64Wasm ran at 2-6 fps (retail ROM too). An earlier build with the same pipeline played Dam.
- Level textures are colour grids + noise (default scope); some large signs/posters may still carry text not yet
  transcribed (see find_text ranking beyond the first 120).
- Mission thumbnails are simple drawn scenes; could be renders of each level's own geometry.
- HUD/watch menu not yet reviewed in detail; legal screen / Nintendo logo check.
- Headless speed varies a lot with machine load; a real browser should be 60 fps on menus.

## For the morning
1. Open the live link in a desktop browser (keyboard: arrows move, A fire, D use, Enter start; or a gamepad) and play
   Dam. Tell me what looks/sounds worst.
2. Voices (optional, 6 short grunts/screams): `D:/n64work/goldeneye/practice/SCRIPT.txt` + call-and-response
   tracks. Save takes as `games/goldeneye/overrides/sounds/sfx/<slot>.wav` and I'll rebuild.
