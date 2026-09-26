/*
 * tex2raw (dirty room only): decode GoldenEye image-bank textures to raw native pixels.
 *
 *   tex2raw out.bin file1.bin [file2.bin ...]
 *
 * Record per input: "TEX1", u8 header byte, u8 nlevels, u32 consumed bytes,
 * u16 numcolours, palette (numcolours * 2 bytes, zlib textures only), then per level:
 * u8 format, u8 method (255 = zlib/CI), u16 w, u16 h, u8 packed4, u32 len, pixels.
 * packed4 = 1 when 4-bit formats hold two pixels per byte (else one value per byte).
 * The decoder is the decomp's libpdtex reader (tools/mktex) with puff instead of zlib.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pdtex.h"

int g_TexFormatNumChannels[] = { 4, 3, 3, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1 };
int g_TexFormatHas1BitAlpha[] = { 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0 };
int g_TexFormatChannelSizes[] = { 256, 32, 256, 32, 256, 16, 8, 256, 16, 256, 16, 256, 16 };
int g_TexFormatBitsPerPixel[] = { 32, 16, 24, 15, 16, 8, 4, 8, 4, 16, 16, 16, 16 };

extern int g_Consumed, g_Header;
int reader_read(FILE *fp, struct pd_tex *tex);

static void w8(FILE *f, int v) { fputc(v & 0xff, f); }
static void w16(FILE *f, int v) { w8(f, v >> 8); w8(f, v); }
static void w32(FILE *f, int v) { w16(f, v >> 16); w16(f, v); }

static int levelbytes(struct pd_image *im, int *packed4)
{
	int n = im->width * im->height;
	*packed4 = 0;
	if (im->compression == 255) return n;
	switch (im->format) {
	case PDFORMAT_RGBA32: return n * 4;
	case PDFORMAT_RGB24: return n * 3;
	case PDFORMAT_RGBA16: case PDFORMAT_IA16: case PDFORMAT_RGB15: return n * 2;
	case PDFORMAT_IA8: case PDFORMAT_I8: return n;
	case PDFORMAT_I4:
		if (im->compression == 2 || im->compression == 3 || im->compression == 4 ||
		    im->compression == 8 || im->compression == 9) return n; /* channel paths: memcpy */
		*packed4 = 1; return (im->width + 1) / 2 * im->height;
	case PDFORMAT_IA4:
		*packed4 = 1; return (im->width + 1) / 2 * im->height;
	}
	return n * 2; /* CI formats via non-zlib paths: not expected */
}

static const char CRLF[] = { 13, 10, 0 };

int main(int argc, char **argv)
{
	FILE *out = fopen(argv[1], "wb");
	int i, j, bad = 0;

	static char names[4096][256];
	int count = 0;

	/* tex2raw out.bin @list.txt  (one path per line) or paths on the command line */
	for (i = 2; i < argc; i++) {
		if (argv[i][0] == '@') {
			FILE *lf = fopen(argv[i] + 1, "r");
			while (lf && count < 4096 && fgets(names[count], 256, lf)) {
				names[count][strcspn(names[count], CRLF)] = 0;
				if (names[count][0]) count++;
			}
			if (lf) fclose(lf);
		} else if (count < 4096) {
			strncpy(names[count++], argv[i], 255);
		}
	}

	for (i = 0; i < count; i++) {
		struct pd_tex *tex = calloc(1, sizeof(*tex));
		FILE *fp = fopen(names[i], "rb");
		int n = 0, p4;

		if (getenv("TEX2RAW_TRACE")) { fprintf(stderr, "%d %s\n", i, names[i]); fflush(stderr); }
		if (!fp) { fprintf(stderr, "cannot open %s\n", names[i]); bad++; continue; }
		reader_read(fp, tex);
		fclose(fp);
		for (j = 0; j < PDTEX_MAX_IMAGES; j++) if (tex->images[j].exists) n = j + 1;
		fwrite("TEX1", 1, 4, out);
		w8(out, g_Header); w8(out, n); w32(out, g_Consumed);
		w16(out, tex->palette ? tex->numcolours : 0);
		if (tex->palette) fwrite(tex->palette, 1, tex->numcolours * 2, out);
		for (j = 0; j < n; j++) {
			struct pd_image *im = &tex->images[j];
			int len = levelbytes(im, &p4);
			w8(out, im->format); w8(out, im->compression); w16(out, im->width); w16(out, im->height);
			w8(out, p4); w32(out, len);
			fwrite(im->pixels, 1, len, out);
		}
		free(tex);
	}
	fclose(out);
	printf("tex2raw: %d files, %d unreadable\n", count, bad);
	return bad != 0;
}
