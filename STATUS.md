# GoldenEye 007 clean room: status

## Decisions (log)
- 2026-09-25 22:42: ROM `GoldenEye 007 (USA).z64` sha1 abe01e4a… = decomp's US target. Decomp n64decomp/007 cloned
  (depth 1, LF) to `D:/n64work/goldeneye/pristine`; dirty tree `D:/n64work/goldeneye/dirty` (baserom + extracted assets).
- **Web route = clean ROM + N64Wasm** (playbook §4 option 3). Why: GoldenEye has no PC port (the decomp still
  has large asm parts), so no Emscripten target; N64Wasm (MIT, ParaLLEl core, prebuilt at
  `C:/Users/andre/n64work/n64wasm/dist`) is already proven on SSB64 with keyboard + gamepad + audio.
- **Build on Windows natively works and matches retail** (23:05): decomp Makefile with
  `IRIX_ROOT=D:/n64work/goldeneye/idoroot` (a `cc` shim -> `tools/idowin/ido_cc.py`, IDO passes from
  `C:/Users/andre/n64work/idowin/bin`), `mips64-elf-*` from `~/.local/mips64/bin`, decomp gzip built with zig
  (binary stdio), armips.exe copied from the SM64 tree, `cpp` shim -> clang -E, and
  `ConvertAIPRINT=python games/goldeneye/build/aiprint.py` (Git's sed mis-handles the decomp's regex).
  `ido_cc.py` gained `-Olimit N` and piped-stdin (`tools/include-stdin.c`) support.
  -> the clean ROM is a real decomp build with regenerated assets (the linker re-lays everything; no packer needed).

## Works
- Dirty round-trip build: sha1 match.

## Next
- Census of extracted assets; decide kept facts per class; generator.

## For the morning
- (nothing yet)
