#!/bin/bash
# Build a decomp tree (dirty or clean) on Windows/Git Bash -> build/u/ge007.u.z64
#   games/goldeneye/build/build.sh <tree> [jobs]
# Needs: tools/setup_winbin.sh shims in ~/bin, mips64-elf binutils in ~/.local/mips64/bin,
# IDO passes (C:/Users/andre/n64work/idowin/bin) driven by tools/idowin/ido_cc.py.
set -e
TREE="$1"; JOBS="${2:-12}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
IDOROOT="$(dirname "$TREE")/idoroot"
mkdir -p "$IDOROOT"
cat > "$IDOROOT/cc" <<EOF
#!/bin/sh
export IDO_BIN=\${IDO_BIN:-C:/Users/andre/n64work/idowin/bin}
exec python "$REPO/tools/idowin/ido_cc.py" "\$@"
EOF
chmod +x "$IDOROOT/cc"
export PATH="$HOME/bin:$HOME/.local/mips64/bin:$PATH"
cd "$TREE"
bash scripts/make/create_directories.sh build/u u >/dev/null 2>&1 || true
make -j"$JOBS" IRIX_ROOT="$IDOROOT" COMPARE=0 \
  "ConvertAIPRINT=python $REPO/games/goldeneye/build/aiprint.py" build/u/ge007.u.z64
ls -la build/u/ge007.u.z64
