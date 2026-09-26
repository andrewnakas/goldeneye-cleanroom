#!/bin/bash
# Publish the site to gh-pages of andrewnakas/goldeneye-cleanroom, gated on the taint scan.
#   games/goldeneye/publish.sh <dirty> <clean> <tex2raw.exe> <retail tex_raw.bin> <site dir>
set -e
DIRTY="$1"; CLEAN="$2"; EXE="$3"; RAW="$4"; SITE="$5"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
python -m games.goldeneye.taint "$DIRTY" "$CLEAN" "$EXE" "$RAW" || { echo "taint failing: not publishing"; exit 1; }
rm -rf "$SITE" && python ports/emu/make_site.py "$SITE" "$CLEAN/build/u/ge007.u.z64"
cd "$SITE"
rm -rf .git && git init -q -b gh-pages && git add -A
git -c user.name=andrewnakas -c user.email=andrewnakas@users.noreply.github.com commit -qm "site: clean-room GoldenEye 007 (N64Wasm + clean ROM)"
git remote add origin https://github.com/andrewnakas/goldeneye-cleanroom.git
git push -f -q origin gh-pages
echo "published gh-pages"
