"""Pictures drawn procedurally from our own descriptions (no retail pixels involved).

gunbarrel(w, h): the rifled gun-barrel spiral behind the folder menus (8-bit intensity,
RLE-packed by rle8() in the game's rle_expand_8bit format).
"""
import numpy as np


def gunbarrel(w=440, h=299, cx=272.0, cy=140.0, seed=7):
    """High-contrast rifling: six spiral lands winding into a bright bore, black outside."""
    y, x = np.mgrid[:h, :w].astype(np.float32)
    dx, dy = x - cx, y - cy
    r = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    R = 330.0
    bore = 58.0
    # spiral lands: the angle winds with log radius, like looking down a rifled barrel
    phase = th * 6.0 + 5.2 * np.log(np.maximum(r, 1.0) / bore)
    land = np.sin(phase)
    # each land is lit on one edge (sharp) and falls into shadow on the other
    lit = (land > 0.05) & (np.cos(phase) > -0.35)
    img = np.where(lit, 255, 0).astype(np.float32)
    # grooves get a few bright specks near the bore (machining marks)
    rng = np.random.default_rng(seed)
    speck = rng.random((h, w)) > 0.985
    img[(speck) & (r < bore * 2.2) & (r > bore)] = 255
    # bright bore with a thin dark ring, fade to black toward the muzzle edge
    img[r < bore] = 255
    ring = (r >= bore) & (r < bore + 4)
    img[ring] = 0
    img[r > R * (0.72 + 0.18 * np.sin(th * 3 + 1.0))] = 0
    # left side falls away into darkness (the barrel is lit from the right)
    img[(x < cx - 190) & (rng.random((h, w)) > 0.1)] = 0
    return img.astype(np.uint8)


def rle8(img, head6=b"\x00\x00\x00\x00\x00\x08"):
    """rle_expand_8bit format: u16 w, u16 h, 6 header bytes, then (count, value) pairs."""
    h, w = img.shape
    out = bytearray(w.to_bytes(2, "big") + h.to_bytes(2, "big") + head6)
    flat = img.reshape(-1)
    i = 0
    while i < len(flat):
        v = flat[i]
        n = 1
        while i + n < len(flat) and flat[i + n] == v and n < 255:
            n += 1
        out += bytes([n, int(v)])
        i += n
    while len(out) % 16:
        out.append(0)
    return bytes(out)
