# Taint scan evidence

Verbatim output of the last taint scan saved in the local work directory, committed as evidence.
It was not re-run for this commit; check the log date against the date of the published build.

Command: `python -m games.goldeneye.taint "$DIRTY" "$CLEAN" "$EXE" "$RAW" (inside the publish script; log = D:/n64work/goldeneye/pub.log)`

Live-build check (2026-10-19): the published `game.z64` (git blob defa04b664) equals `D:/n64work/goldeneye/clean/build/u/ge007.u.z64`. That file was rebuilt at 12:07, eight hours after this scan of the 03:59 build; the bytes are probably the same but this is not proven.

## `pub.log` (written 2026-09-26 04:00)

```
python /d/n64work/goldeneye-cleanroom/games/goldeneye/build/aiprint.py assets/font_chardataj.c | D:/n64work/goldeneye/idoroot/cc -c -Wab,-r4300_mul -non_shared -Olimit 2000 -G 0 -Xcpluscomm  -woff 609,649,709,712,807,838,763 -I . -I include -I include/ultra64 -I include/PR -I src -I src/game -I src/inflate -mips2 -32 -DVERSION_US -DLANG_US -DREFRESH_NTSC -DLEFTOVERDEBUG -DLEFTOVERSPECTRUM -DBUGFIX_R0 -DBYTEMATCH -DTARGET_N64 tools/include-stdin.c -o build/u/assets/font_chardataj.o -O2
python /d/n64work/goldeneye-cleanroom/games/goldeneye/build/aiprint.py assets/font_chardatae.c | D:/n64work/goldeneye/idoroot/cc -c -Wab,-r4300_mul -non_shared -Olimit 2000 -G 0 -Xcpluscomm  -woff 609,649,709,712,807,838,763 -I . -I include -I include/ultra64 -I include/PR -I src -I src/game -I src/inflate -mips2 -32 -DVERSION_US -DLANG_US -DREFRESH_NTSC -DLEFTOVERDEBUG -DLEFTOVERSPECTRUM -DBUGFIX_R0 -DBYTEMATCH -DTARGET_N64 tools/include-stdin.c -o build/u/assets/font_chardatae.o -O2
D:/n64work/goldeneye/idoroot/cc -c -Wab,-r4300_mul -non_shared -Olimit 2000 -G 0 -Xcpluscomm  -woff 609,649,709,712,807,838,763 -I . -I include -I include/ultra64 -I include/PR -I src -I src/game -I src/inflate -mips2 -32 -DVERSION_US -DLANG_US -DREFRESH_NTSC -DLEFTOVERDEBUG -DLEFTOVERSPECTRUM -DBUGFIX_R0 -DBYTEMATCH -DTARGET_N64 -o build/u/assets/font/fontBankGothic.o -O2 assets/font/fontBankGothic.c
D:/n64work/goldeneye/idoroot/cc -c -Wab,-r4300_mul -non_shared -Olimit 2000 -G 0 -Xcpluscomm  -woff 609,649,709,712,807,838,763 -I . -I include -I include/ultra64 -I include/PR -I src -I src/game -I src/inflate -mips2 -32 -DVERSION_US -DLANG_US -DREFRESH_NTSC -DLEFTOVERDEBUG -DLEFTOVERSPECTRUM -DBUGFIX_R0 -DBYTEMATCH -DTARGET_N64 -o build/u/assets/font/fontZurichBold.o -O2 assets/font/fontZurichBold.c
cpp -DVERSION_US -DOUTCODE=u -P ge007.ld -o build/u/ge007.u.ld
Linking Files into ELF
mips64-elf-ld -T build/u/ge007.u.ld -Map build/u/ge007.u.map --no-warn-mismatch -o build/u/ge007.u.elf
Building ROM
mips64-elf-objcopy build/u/ge007.u.elf build/u/ge007.u.bin -O binary --gap-fill=0xff
Compressing ROM
tools/data_compress.sh build/u/ge007.u.bin u
D:\n64work\goldeneye\clean\tools\data_compress.sh: line 6: printf: 0x: invalid hex number
patching build/u/ge007.u.bin
extract data segment
truncate build/u/ge007.u.bin to 0xc00000
compress data segment
inject data segment
size=71724
maxsize=72704
Finalizing ROM
tools/n64cksum build/u/ge007.u.bin build/u/ge007.u.z64
-rw-r--r-- 1 andre 197609 12582912 Sep 26 03:59 build/u/ge007.u.z64
textures: 2698 decoded, 0 failed []
taint: 7533 generated streams scanned, 21 with shared windows, 0 failing
  worst ('tex1201.0', 21, 18, 29)
  worst ('file:assets/images/split/FIRE_5.bin', 6, 6, 21)
  worst ('tex1504.0', 1941, 4, 19)
site -> D:/n64work/goldeneye/pubsite
warning: in the working copy of 'n64wasm.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'vendor/FileSaver.min.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'vendor/bootstrap.min.css', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'vendor/bootstrap.min.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'vendor/jquery-3.3.1.min.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'vendor/popper.min.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'vendor/rivets.bundled.min.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'vendor/toastr.min.js', LF will be replaced by CRLF the next time Git touches it
published gh-pages
```
