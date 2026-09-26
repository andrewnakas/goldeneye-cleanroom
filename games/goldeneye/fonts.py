"""Menu/HUD fonts (assets/font/fontBankGothic.c, fontZurichBold.c) with our own glyphs.

Kept (layout facts from the decomp's tables): the 13x13 kerning classes, and per character its
index, baseline offset, cell height/width and kerning class. Generated: every glyph pixel, drawn
with the project's stroke font fitted to the cell (I8 coverage, like the game's glyph format).
The Japanese/multibyte glyph banks (font_chardataj.c/e.c, used only by the Japanese language)
become plain box glyphs.

    python -m games.goldeneye.fonts <pristine> <clean> [--preview out.png]
"""
import os
import re
import sys

import numpy as np

from cleanroom.gfx import strokefont

# glyphs the shared stroke font lacks (4 x 6 design grid, y down)
EXTRA = {
    "$": [[(4, 1), (3, 0.5), (1, 0.5), (0, 1.5), (0, 2.5), (4, 3.5), (4, 4.8), (3, 5.5), (1, 5.5), (0, 5)],
          [(2, -0.3), (2, 6.3)]],
    ";": [[(0.6, 2.5), (0.6, 2.5)], [(0.6, 5.4), (0, 7)]],
    "@": [[(3, 4), (3, 2), (1.6, 2), (1.2, 3), (1.6, 4), (4, 4), (4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (4, 6)]],
    "[": [[(1.2, 0), (0, 0), (0, 6), (1.2, 6)]],
    "]": [[(0, 0), (1.2, 0), (1.2, 6), (0, 6)]],
    "^": [[(0, 2), (1.5, 0), (3, 2)]],
    "_": [[(0, 6), (4, 6)]],
    "`": [[(0, 0), (1, 1.2)]],
    "{": [[(1.6, 0), (0.8, 0.4), (0.8, 2.6), (0, 3), (0.8, 3.4), (0.8, 5.6), (1.6, 6)]],
    "}": [[(0, 0), (0.8, 0.4), (0.8, 2.6), (1.6, 3), (0.8, 3.4), (0.8, 5.6), (0, 6)]],
    "|": [[(0, 0), (0, 6)]],
    "~": [[(0, 3.2), (1, 2.6), (2, 3.2), (3, 2.6)]],
}


def glyph_lines(c):
    return EXTRA.get(c) or strokefont.glyph(c)


def fit_glyph(c, w, h, th=None):
    """Coverage mask (h, w) of c with its design bounding box stretched to the cell.

    The game's cells are tight boxes around the ink, so fitting bbox -> cell puts caps,
    x-height and descenders where the layout (baseline offsets) expects them."""
    mask = np.zeros((h, w), np.float32)
    lines = glyph_lines(c)
    if not lines or w < 1 or h < 1:
        return mask
    xs = [x for ln in lines for x, _ in ln]
    ys = [y for ln in lines for _, y in ln]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if th is None:
        th = max(0.55, min(w, h) * 0.11, h * 0.085)
    th = min(th, max(0.5, (min(w, h) - 1) / 2.2))
    pad = th * 0.9
    sx = (w - 2 * pad) / (x1 - x0) if x1 > x0 else 0.0
    sy = (h - 2 * pad) / (y1 - y0) if y1 > y0 else 0.0
    ox = pad - x0 * sx if x1 > x0 else w / 2.0
    oy = pad - y0 * sy if y1 > y0 else h / 2.0
    return strokefont._stroke(mask, lines, ox, oy, sx, sy, th)


def parse_u32_arrays(src):
    """{name: [u32...]} for every `u32 name[] = {...};` in a C file."""
    out = {}
    for m in re.finditer(r"u32\s+(\w+)\s*\[[^\]]*\]\s*=\s*\{(.*?)\};", src, re.S):
        body = re.sub(r"//.*|/\*.*?\*/", "", m.group(2), flags=re.S)
        out[m.group(1)] = [int(v, 0) for v in re.findall(r"0x[0-9A-Fa-f]+|\d+", body)]
    return out


def regenerate_font(path_in, path_out, prefix):
    src = open(path_in).read()
    arr = parse_u32_arrays(src)
    table = arr[prefix + "_fontchartable"]
    nbytes = len(arr[prefix + "_fontbytes"]) * 4
    # struct offset of fontbytes: the arrays before it (kerning, char table) are packed, no padding
    names = list(arr)
    base = 4 * sum(len(arr[n]) for n in names[:names.index(prefix + "_fontbytes")])
    data = bytearray(nbytes)
    cells = []
    for k in range(len(table) // 6):
        idx, baseline, h, w, kern, off = table[k * 6:k * 6 + 6]
        stride = (w + 7) & ~7
        ch = chr(0x21 + idx)
        m = fit_glyph(ch, w, h)
        cell = np.zeros((h, stride), np.uint8)
        cell[:, :w] = np.clip(m * 255 + 0.5, 0, 255).astype(np.uint8)
        o = off - base
        data[o:o + stride * h] = cell.tobytes()
        cells.append((ch, cell[:, :w]))
    words = np.frombuffer(bytes(data), ">u4")
    body = ",\n".join("    " + ", ".join("0x%08X" % v for v in words[i:i + 8]) for i in range(0, len(words), 8))
    new = re.sub(r"(u32\s+" + prefix + r"_fontbytes\s*\[\s*\d*\s*\]\s*=\s*\{)(.*?)(\};)",
                 lambda m: m.group(1) + "\n" + body + "\n" + m.group(3), src, count=1, flags=re.S)
    open(path_out, "w", newline="\n").write(new)
    return cells


def box_glyphs(path_in, path_out, cell_bytes):
    """Japanese / multibyte glyph banks: same array names and sizes, a hollow box per cell."""
    src = open(path_in).read()

    def repl(m):
        n = len(re.findall(r"0x[0-9A-Fa-f]+", m.group(2)))
        nb = n * 4
        # 4-bit pixels, 16 px per row (8 bytes): outline box inset by one pixel
        rows = nb // 8
        img = np.zeros((rows, 16), np.uint8)
        if rows >= 4:
            img[1, 2:14] = 12
            img[rows - 2, 2:14] = 12
            img[1:rows - 1, 2] = 12
            img[1:rows - 1, 13] = 12
        packed = (img[:, 0::2] << 4) | img[:, 1::2]
        words = np.frombuffer(packed.tobytes()[:nb].ljust(nb, b"\0"), ">u4")
        return m.group(1) + ",".join("0x%08x" % v for v in words) + m.group(3)

    new = re.sub(r"(u32\s+\w+\s*\[\s*\d*\s*\]\s*=\s*\{\s*)(.*?)(\s*\};)", repl, src, flags=re.S)
    open(path_out, "w", newline="\n").write(new)


def preview(cells_by_font, out):
    from cleanroom.gfx import png
    rows = []
    for cells in cells_by_font:
        H = max(c.shape[0] for _, c in cells) + 4
        W = sum(c.shape[1] + 2 for _, c in cells) + 4
        img = np.zeros((H, W), np.uint8)
        x = 2
        for _, c in cells:
            img[2:2 + c.shape[0], x:x + c.shape[1]] = c
            x += c.shape[1] + 2
        rows.append(img)
    W = max(r.shape[1] for r in rows)
    sheet = np.concatenate([np.pad(r, ((0, 0), (0, W - r.shape[1]))) for r in rows], 0)
    sheet = sheet.repeat(3, 0).repeat(3, 1)
    png.write(out, np.stack([sheet] * 3 + [np.full_like(sheet, 255)], -1))


def main(argv):
    pristine, clean = argv[0], argv[1]
    cells = []
    for name, prefix in (("fontBankGothic", "fontBankGothic"), ("fontZurichBold", "fontZurichBold")):
        cells.append(regenerate_font(os.path.join(pristine, f"assets/font/{name}.c"),
                                     os.path.join(clean, f"assets/font/{name}.c"), prefix))
    for n in ("font_chardataj.c", "font_chardatae.c"):
        box_glyphs(os.path.join(pristine, "assets", n), os.path.join(clean, "assets", n), 0)
    print(f"fonts: {sum(len(c) for c in cells)} glyphs drawn, Japanese/multibyte banks boxed")
    if "--preview" in argv:
        preview(cells, argv[argv.index("--preview") + 1])


if __name__ == "__main__":
    main(sys.argv[1:])
