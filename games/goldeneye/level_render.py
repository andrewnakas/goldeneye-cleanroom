"""Mission thumbnails rendered from each level's own geometry (bg room vertex tables + display
lists, kept facts), as grey aerial "recon photos". Lighting = the rooms' baked vertex colours.

    python -m games.goldeneye.level_render preview <tree> <out.png>

Rooms in bg_<name>_all_p.c: point_table_binary_N (Vtx, 1172-compressed) and pri_mapping_binary_N
(F3D display list: 0x04 G_VTX with segment 0x0E offsets into the room's table, 0xB1 G_TRI4, 0xBF TRI1),
placed at the room table's position.
"""
import os
import re
import struct
import sys
import zlib

import numpy as np

# thumbnail -> bg file (src/game/bg.c level table)
LEVEL_BG = {"DAM": "dam", "FACILITY": "ark", "RUNWAY": "run", "SURFACEI": "sevx", "SURFACEII": "sevx",
            "BUNKERI": "sev", "BUNKERII": "sevb", "SILO": "silo", "FRIGATE": "dest", "STATUE": "stat",
            "ARCHIVES": "arch", "DEPOT": "depo", "CONTROL": "arec", "CAVERNS": "cave",
            "AZTEC": "azt", "EGYPT": "cryp",
            "MP_TEMPLE": "dish", "MP_COMPLEX": "ref", "MP_CAVES": "oat", "MP_BASEMENT": "ame"}


def _inflate(b):
    assert b[:2] == b"\x11\x72", b[:4]
    return zlib.decompressobj(-15).decompress(b[2:])


def load_rooms(tree, name):
    """[(verts Nx3 float world, colours N, tris Mx3 int)] per room."""
    path = os.path.join(tree, f"assets/obseg/bg/bg_{name}_all_p.c")
    if not os.path.exists(path):
        return None
    src = open(path).read()
    arrays = {m.group(1): m.group(2) for m in re.finditer(r"u32\s+(\w+)\[\]\s*=\s*\{(.*?)\};", src, re.S)}

    def blob(n):
        return np.asarray([int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]+", arrays[n])], ">u4").tobytes()

    table = re.search(r"room_data_table\[\]\s*=\s*\{(.*?)\};", src, re.S).group(1)
    rooms = []
    for m in re.finditer(r"\{&(point_table_binary_\d+),\s*&(pri_mapping_binary_\d+),\s*[^,]+,\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\}", table):
        try:
            vt = _inflate(blob(m.group(1)))
            dl = _inflate(blob(m.group(2)))
        except Exception:
            continue
        pos = np.array([float(m.group(3)), float(m.group(4)), float(m.group(5))], np.float32)
        nv = len(vt) // 16
        v = np.frombuffer(vt[:nv * 16], np.dtype([("x", ">i2"), ("y", ">i2"), ("z", ">i2"), ("f", ">i2"),
                                                  ("s", ">i2"), ("t", ">i2"), ("r", "u1"), ("g", "u1"),
                                                  ("b", "u1"), ("a", "u1")]))
        xyz = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float32) + pos
        col = (v["r"].astype(np.float32) * 0.3 + v["g"] * 0.59 + v["b"] * 0.11)
        cache = [0] * 32
        tris = []
        for i in range(0, len(dl) - 7, 8):
            w0, w1 = struct.unpack_from(">II", dl, i)
            op = w0 >> 24
            if op == 0x04:
                n = ((w0 >> 20) & 15) + 1
                v0 = (w0 >> 16) & 15
                base = (w1 & 0xFFFFFF) // 16
                for j in range(n):
                    cache[v0 + j] = min(base + j, nv - 1)
            elif op == 0xB1:
                for k in range(4):
                    x = (w1 >> (8 * k)) & 15
                    y = (w1 >> (8 * k + 4)) & 15
                    z = (w0 >> (4 * k)) & 15
                    if x or y or z:
                        tris.append((cache[x], cache[y], cache[z]))
            elif op == 0xBF:
                a, b, c = ((w1 >> 16) & 0xFF) // 10, ((w1 >> 8) & 0xFF) // 10, (w1 & 0xFF) // 10
                tris.append((cache[a], cache[b], cache[c]))
            elif op == 0xB8:
                break
        if tris:
            rooms.append((xyz, col, np.asarray(tris, np.int32)))
    return rooms


def render(rooms, W, H, elev=1.15, azim=None):
    """Software z-buffer render from above-and-outside the level, looking at its centre."""
    P = np.concatenate([r[0] for r in rooms])
    C = np.concatenate([r[1] for r in rooms])
    T = np.concatenate([r[2] + off for r, off in zip(rooms, np.cumsum([0] + [len(r[0]) for r in rooms[:-1]]))])
    lo, hi = np.percentile(P, 2, 0), np.percentile(P, 98, 0)
    centre = (lo + hi) / 2
    ext = np.linalg.norm(hi - lo)
    if azim is None:     # look across the longer side, so it spans the frame
        azim = np.pi / 2 if (hi[0] - lo[0]) > (hi[2] - lo[2]) else 0.0
    d = np.array([np.cos(azim) * np.cos(elev), np.sin(elev), np.sin(azim) * np.cos(elev)], np.float32)
    eye = centre + d * ext * 0.75
    f = centre - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    rel = P - eye
    cx, cy, cz = rel @ r, rel @ u, rel @ f
    z = np.maximum(cz, 1.0)
    # fit: scale so the middle 96% of the geometry spans the frame
    front = cz > 1
    px, py = cx[front] / z[front], cy[front] / z[front]
    spanx = np.percentile(px, 98) - np.percentile(px, 2)
    spany = np.percentile(py, 98) - np.percentile(py, 2)
    focal = 0.92 * min(W / max(spanx, 1e-3), H * 0.8 / max(spany, 1e-3))
    midx = (np.percentile(px, 98) + np.percentile(px, 2)) / 2
    midy = (np.percentile(py, 98) + np.percentile(py, 2)) / 2
    cx = cx - midx * z
    cy = cy - midy * z - 0.08 * H / focal * z
    sx = W / 2 + cx / z * focal
    sy = H / 2 - cy / z * focal
    img = np.full((H, W), 45.0, np.float32)                              # ground below the level
    zbuf = np.full((H, W), np.inf, np.float32)
    for a, b, c in T:
        if cz[a] < 1 or cz[b] < 1 or cz[c] < 1:
            continue
        xs = np.array([sx[a], sx[b], sx[c]])
        ys = np.array([sy[a], sy[b], sy[c]])
        x0, x1 = int(max(0, np.floor(xs.min()))), int(min(W - 1, np.ceil(xs.max())))
        y0, y1 = int(max(0, np.floor(ys.min()))), int(min(H - 1, np.ceil(ys.max())))
        if x0 > x1 or y0 > y1:
            continue
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(den) < 1e-9:
            continue
        gy, gx = np.mgrid[y0:y1 + 1, x0:x1 + 1].astype(np.float32) + 0.5
        l0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
        l1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
        l2 = 1 - l0 - l1
        m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not m.any():
            continue
        zz = l0 * z[a] + l1 * z[b] + l2 * z[c]
        cc = l0 * C[a] + l1 * C[b] + l2 * C[c]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = m & (zz < sub)
        sub[upd] = zz[upd]
        img[y0:y1 + 1, x0:x1 + 1][upd] = cc[upd]
    # photo look: contrast stretch + slight fog with distance
    fin = np.isfinite(zbuf)
    if fin.any():
        zn = (zbuf - zbuf[fin].min()) / (np.ptp(zbuf[fin]) + 1e-6)
        img[fin] = img[fin] * (1 - 0.35 * zn[fin]) + 170 * 0.35 * zn[fin]
    lo_, hi_ = np.percentile(img, 2), np.percentile(img, 98)
    img = np.clip((img - lo_) / max(1, hi_ - lo_) * 235 + 10, 0, 255)
    return img


def thumbnail(tree, key, W, H):
    name = LEVEL_BG.get(key)
    if not name:
        return None
    rooms = load_rooms(tree, name)
    if not rooms:
        return None
    g = render(rooms, W, H)
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = g[..., None]
    out[..., 3] = 255
    return out


def preview(tree, out):
    from cleanroom.gfx import png
    tiles = []
    for key in LEVEL_BG:
        t = thumbnail(tree, key, 128, 128)
        if t is not None:
            tiles.append(np.pad(t, ((2, 2), (2, 2), (0, 0))))
            print(key, "ok")
        else:
            print(key, "no geometry")
    cols = 6
    rows = [np.concatenate(tiles[i:i + cols] + [np.zeros_like(tiles[0])] * (cols - len(tiles[i:i + cols])), 1)
            for i in range(0, len(tiles), cols)]
    sheet = np.concatenate(rows, 0)
    sheet[..., 3] = 255
    png.write(out, sheet.clip(0, 255).astype(np.uint8))


if __name__ == "__main__":
    preview(sys.argv[2], sys.argv[3])


_cache = {}


def override(t, tree):
    """Level-0 RGBA (GE storage order) for mission (X_U / X_L) and MP (MP_X) thumbnails, or None."""
    import re as _re
    f, w, h = t["levels"][0]
    m = _re.fullmatch(r"([A-Z]+I*)_(U|L)", t["name"])
    if m and m.group(1) in LEVEL_BG:
        key = m.group(1)
        if key not in _cache:
            _cache[key] = thumbnail(tree, key, w, 2 * h)
        full = _cache[key]
        if full is None:
            return None
        part = full[:h] if m.group(2) == "U" else full[h:]
        return np.ascontiguousarray(part[::-1])
    if t["name"].startswith("MP_"):
        short = t["name"][3:]
        key = t["name"] if t["name"] in LEVEL_BG else {"BUNKER": "BUNKERI", "BUNKER2": "BUNKERII", "SURFACE": "SURFACEI",
                                                       "SURFACE2": "SURFACEII"}.get(short, short)
        img = thumbnail(tree, key, w, h) if key in LEVEL_BG else None
        return None if img is None else np.ascontiguousarray(img[::-1])
    return None
