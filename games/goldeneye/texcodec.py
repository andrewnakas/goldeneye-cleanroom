"""GoldenEye image-bank texture format: raw-dump reader (dirty room) and encoder (clean room).

Header byte: e z llllll  (e = explicit levels, z = zlib/paletted, l = level count)
Non-zlib level: ffff wwwwwwww hhhhhhhh cccc  + data  (format, width, height, method)
Zlib level (after a shared format byte + palette): wwwwwwww hhhhhhhh + 1172 deflate of indices.
Formats (GE image.c): 0 RGBA32, 1 RGBA16, 2 RGB24, 3 RGB15, 4 IA16, 5 IA8, 6 IA4, 7 I8, 8 I4,
9 RGBA16_CI8, 10 RGBA16_CI4, 11 IA16_CI8, 12 IA16_CI4.
"""
import struct
import zlib

import numpy as np

FMT_NAMES = ["rgba32", "rgba16", "rgb24", "rgb15", "ia16", "ia8", "ia4", "i8", "i4",
             "rgba16_ci8", "rgba16_ci4", "ia16_ci8", "ia16_ci4"]
BITS_PER_PIXEL = [32, 16, 24, 15, 16, 8, 4, 8, 4, 16, 16, 16, 16]


# ---------------------------------------------------------------- raw dump (tex2raw) reader

def read_raw_dump(path):
    """Yield dicts from tex2raw's output: header, consumed, palette (u16 list), levels."""
    data = open(path, "rb").read()
    pos = 0
    while pos < len(data):
        assert data[pos:pos + 4] == b"TEX1", pos
        hdr, n, consumed, ncol = struct.unpack_from(">BBIH", data, pos + 4)
        pos += 12
        pal = list(struct.unpack_from(">%dH" % ncol, data, pos)) if ncol else []
        pos += 2 * ncol
        levels = []
        for _ in range(n):
            fmt, meth, w, h, p4, ln = struct.unpack_from(">BBHHBI", data, pos)
            pos += 11
            levels.append({"format": fmt, "method": meth, "w": w, "h": h, "packed4": p4,
                           "raw": data[pos:pos + ln]})
            pos += ln
        yield {"header": hdr, "consumed": consumed, "palette": pal, "levels": levels}


def _rgba16(v):
    v = np.asarray(v, dtype=np.uint32)
    r = (v >> 11) & 31
    g = (v >> 6) & 31
    b = (v >> 1) & 31
    a = v & 1
    return np.stack([r * 255 // 31, g * 255 // 31, b * 255 // 31, a * 255], -1).astype(np.uint8)


def _ia16(v):
    v = np.asarray(v, dtype=np.uint32)
    i = v >> 8
    return np.stack([i, i, i, v & 255], -1).astype(np.uint8)


def level_rgba(lv, palette):
    """Native level pixels -> HxWx4 uint8 RGBA."""
    f, w, h, raw = lv["format"], lv["w"], lv["h"], lv["raw"]
    n = w * h
    b = np.frombuffer(raw, dtype=np.uint8)
    if lv["method"] == 255:  # zlib: one palette index per byte
        pal = np.array(palette + [0] * (256 - len(palette)), dtype=np.uint32)
        vals = pal[b[:n]]
        px = _ia16(vals) if f in (11, 12) else _rgba16(vals)
    elif f == 0:
        px = b[:n * 4].reshape(n, 4)
    elif f == 2:
        px = np.concatenate([b[:n * 3].reshape(n, 3), np.full((n, 1), 255, np.uint8)], 1)
    elif f in (1, 3):
        px = _rgba16(b[:n * 2].view(">u2"))
    elif f == 4:
        px = _ia16(b[:n * 2].view(">u2"))
    elif f == 5:
        i = (b[:n] >> 4) * 17
        a = (b[:n] & 15) * 17
        px = np.stack([i, i, i, a], -1)
    elif f == 7:
        px = np.stack([b[:n]] * 3 + [np.full(n, 255, np.uint8)], -1)
    elif f in (6, 8):
        if lv["packed4"]:
            rowb = (w + 1) // 2
            nib = np.stack([b >> 4, b & 15], -1).reshape(h, rowb * 2)[:, :w].reshape(-1)
        else:
            nib = b[:n]
        if f == 8:
            i = nib * 17
            px = np.stack([i, i, i, np.full(n, 255, np.uint8)], -1)
        else:
            i = ((nib >> 1) * 255 // 7).astype(np.uint8)
            a = (nib & 1) * 255
            px = np.stack([i, i, i, a], -1)
    else:
        px = np.zeros((n, 4), np.uint8)
    return np.ascontiguousarray(px.reshape(h, w, 4).astype(np.uint8))


# ---------------------------------------------------------------- encoder (clean room)

class BitWriter:
    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.n = 0

    def put(self, v, bits):
        for k in range(bits - 1, -1, -1):
            self.acc = (self.acc << 1) | ((v >> k) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.acc)
                self.acc = 0
                self.n = 0

    def put_many(self, values, bits):
        """Fast path for many equal-width fields."""
        if bits == 0:
            return
        v = np.asarray(values, dtype=np.uint32)
        bitarr = ((v[:, None] >> np.arange(bits - 1, -1, -1, dtype=np.uint32)) & 1).astype(np.uint8).reshape(-1)
        start = 0
        if self.n:
            need = 8 - self.n
            for bit in bitarr[:need]:
                self.put(int(bit), 1)
            start = need
        tail = bitarr[start:]
        full = len(tail) // 8 * 8
        if full:
            self.out += np.packbits(tail[:full]).tobytes()
        for bit in tail[full:]:
            self.put(int(bit), 1)

    def align(self):
        """End of a level: the decoder skips to the next whole byte."""
        if self.n:
            self.out.append(self.acc << (8 - self.n))
            self.acc = 0
            self.n = 0
        else:
            # decoder advances one byte when its bit count is 0 (see texInflateNonZlib)
            self.out.append(0)

    def bytes(self):
        return bytes(self.out) + (bytes([self.acc << (8 - self.n)]) if self.n else b"")


def bitsize(n):
    """texGetBitSize: bits needed for indices 0..n-1."""
    c, d = 0, n - 1
    while d > 0:
        d >>= 1
        c += 1
    return c


def rgba_to_native(px, fmt):
    """HxWx4 uint8 -> list of per-pixel integer values at the format's lookup bit width."""
    p = px.reshape(-1, 4).astype(np.uint32)
    r, g, b, a = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
    i = (r * 299 + g * 587 + b * 114) // 1000
    if fmt == 0:
        return (r << 24) | (g << 16) | (b << 8) | a
    if fmt == 2:
        return (r << 16) | (g << 8) | b
    if fmt == 1:
        return ((r >> 3) << 11) | ((g >> 3) << 6) | ((b >> 3) << 1) | (a >= 128)
    if fmt == 3:  # 15-bit: rgb555 (decoder appends the alpha bit)
        return ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)
    if fmt == 4:
        return (i << 8) | a
    if fmt == 5:
        return ((i >> 4) << 4) | (a >> 4)
    if fmt == 7:
        return i
    if fmt == 8:
        return i >> 4
    if fmt == 6:
        return ((i >> 5) << 1) | (a >= 128)
    raise ValueError(fmt)


def encode_lookup(bw, px, fmt):
    """TEXCOMPMETHOD_LOOKUP (5): 11-bit colour count, colours, fixed-width indices."""
    vals = rgba_to_native(px, fmt)
    colours, idx = np.unique(vals, return_inverse=True)
    bpp = BITS_PER_PIXEL[fmt]
    bw.put(len(colours), 11)
    if bpp <= 24:
        bw.put_many(colours, bpp)
    else:
        for c in colours:
            bw.put(int(c) >> 8, 24)
            bw.put(int(c) & 0xff, bpp - 24)
    bw.put_many(idx, bitsize(len(colours)))


def encode_level_nonzlib(bw, px, fmt):
    h, w = px.shape[:2]
    bw.put(fmt, 4)
    bw.put(w, 8)
    bw.put(h, 8)
    bw.put(5, 4)
    encode_lookup(bw, px, fmt)
    bw.align()


def encode_nonzlib(header, levels):
    """levels: list of (fmt, HxWx4 uint8). Returns bytes."""
    bw = BitWriter()
    bw.put(header & 0xbf, 8)
    for fmt, px in levels:
        encode_level_nonzlib(bw, px, fmt)
    return bw.bytes()


def rare_deflate(data):
    """1172 container: 0x11 0x72 + raw deflate."""
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 9)
    return b"\x11\x72" + c.compress(bytes(data)) + c.flush()


def encode_zlib(header, fmt, palette, levels):
    """Paletted texture. palette: list of u16; levels: list of HxW index arrays (uint8)."""
    out = bytearray([header | 0x40, fmt, len(palette) - 1])
    for c in palette:
        out += struct.pack(">H", c)
    for idx in levels:
        h, w = idx.shape
        out += bytes([w, h])
        if fmt in (10, 12):  # CI4: two indices per byte, rows padded to a byte
            rowb = (w + 1) // 2
            pad = np.zeros((h, rowb * 2), np.uint8)
            pad[:, :w] = idx
            packed = (pad[:, 0::2] << 4) | pad[:, 1::2]
            out += rare_deflate(packed.tobytes())
        else:
            out += rare_deflate(idx.astype(np.uint8).tobytes())
    return bytes(out)
