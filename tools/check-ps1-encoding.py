"""PowerShell 5.1 reads UTF-8 without a BOM using the system ANSI code page.

Scripts that contain non-ASCII text must start with a UTF-8 BOM so Windows
PowerShell 5.1 parses them. ASCII scripts do not need a BOM.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".venv", "node_modules", ".git"}


def main() -> int:
    failed = False
    for path in sorted(ROOT.rglob("*.ps1")):
        if any(part in SKIP for part in path.parts):
            continue
        data = path.read_bytes()
        has_bom = data.startswith(b"\xef\xbb\xbf")
        body = data[3:] if has_bom else data
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            print(f"FAIL {path}: not UTF-8 ({exc})")
            failed = True
            continue
        non_ascii = any(ord(char) > 127 for char in text)
        if non_ascii and not has_bom:
            print(f"FAIL {path}: non-ASCII PowerShell script has no UTF-8 BOM")
            failed = True
            continue
        if text.count("{") != text.count("}"):
            print(f"FAIL {path}: unmatched braces")
            failed = True
            continue
        print(f"OK {path.relative_to(ROOT)} bom={has_bom} non_ascii={non_ascii}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
