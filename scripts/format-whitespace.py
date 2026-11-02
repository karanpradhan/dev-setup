"""Normalize trailing whitespace and the final newline in plain config files."""

from pathlib import Path
import sys


def format_file(path):
    original = path.read_bytes()
    # Preserve whitespace escaped by a backslash (meaningful in ignore rules
    # and line continuations). Do not otherwise parse or rewrite config syntax.
    lines = []
    for line in original.split(b"\n"):
        stripped = line.rstrip(b" \t\r")
        lines.append(line if stripped.endswith(b"\\") else stripped)
    formatted = b"\n".join(lines).rstrip(b"\n") + b"\n" if original else b""
    if formatted != original:
        path.write_bytes(formatted)


if __name__ == "__main__":
    for filename in sys.argv[1:]:
        format_file(Path(filename))
