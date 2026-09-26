"""Windows stand-in for the decomp's ConvertAIPRINT sed.

PRINT("ab\n") -> AI_PRINT,'a','b','\n','\0',
Usage: python aiprint.py file.c > out   (or reads stdin when no file is given)
"""
import re
import sys

PAT = re.compile(r'(?<![A-Za-z_])PRINT\("((?:[^"\\]|\\.)*)"\)')


def conv(m):
    s, out, i = m.group(1), [], 0
    while i < len(s):
        if s[i] == "\\":
            out.append("'\\" + s[i + 1] + "'")
            i += 2
        else:
            c = s[i]
            out.append("'\\''" if c == "'" else "'" + c + "'")
            i += 1
    return "AI_PRINT," + ",".join(out + ["'\\0'"]) + ","


def main():
    sys.stdout.reconfigure(newline="\n", encoding="latin-1")
    src = open(sys.argv[1], encoding="latin-1").read() if len(sys.argv) > 1 else sys.stdin.read()
    sys.stdout.write(PAT.sub(conv, src))


if __name__ == "__main__":
    main()
