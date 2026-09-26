"""Dirty room: decode every image-bank texture with tex2raw (one process per file; some files
crash the batch decoder through state left by earlier ones) into one raw dump.

    python -m games.goldeneye.dump_textures <dirty tree> <tex2raw.exe> <out.bin>
"""
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor


def main():
    dirty, exe, out = sys.argv[1:4]
    names = [l.split(",")[2] for l in open(os.path.join(dirty, "build/u/imagelist.csv")) if l.strip()]
    tmp = tempfile.mkdtemp(prefix="tex2raw_")

    def one(k):
        o = os.path.join(tmp, "%05d.bin" % k)
        r = subprocess.run([exe, o, os.path.join(dirty, names[k])], capture_output=True)
        return k, r.returncode, o

    bad = []
    with open(out, "wb") as f, ThreadPoolExecutor(8) as ex:
        for k, rc, o in ex.map(one, range(len(names))):
            if rc != 0 or not os.path.exists(o):
                bad.append(names[k])
                f.write(b"TEX1" + bytes([0, 0]) + b"\0\0\0\0\0\0")  # empty record
            else:
                f.write(open(o, "rb").read())
                os.remove(o)
    os.rmdir(tmp) if not os.listdir(tmp) else None
    print(f"textures: {len(names)} decoded, {len(bad)} failed {bad[:5]}")


if __name__ == "__main__":
    main()
