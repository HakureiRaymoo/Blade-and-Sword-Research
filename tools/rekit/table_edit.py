"""Edit one cell of a GBK tab-separated table in place.

The game's data tables are GBK TSV with a header row.  This is the basic tool
for the "mod the original game" workflow: locate a row by any column value, set
another column, write it back with the original line endings and encoding.

    py tools/rekit/table_edit.py --file <t.txt> --row 角色名称=剑客 --get 平时速度
    py tools/rekit/table_edit.py --file <t.txt> --row 角色名称=剑客 --set 平时速度=14
    py tools/rekit/table_edit.py --file <t.txt> --row ID=4 --set HP=1000 --dry
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

ENCODING = "gbk"


def load(path: str) -> tuple[list[str], list[list[str]], bytes]:
    raw = open(path, "rb").read()
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    text = raw.decode(ENCODING, "replace")
    lines = text.split("\r\n" if newline == b"\r\n" else "\n")
    trailer = ""
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        raise SystemExit(f"{path}: empty")
    header = lines[0].split("\t")
    rows = [ln.split("\t") for ln in lines[1:]]
    return header, rows, newline


def save(path: str, header: list[str], rows: list[list[str]], newline: bytes) -> None:
    out = "\t".join(header) + "\n" + "\n".join("\t".join(r) for r in rows) + "\n"
    data = out.replace("\n", newline.decode())
    open(path, "wb").write(data.encode(ENCODING))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--row", required=True, help="column=value used to pick the row")
    ap.add_argument("--get", default="")
    ap.add_argument("--set", default="", help="column=value to write")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args(argv)

    header, rows, newline = load(a.file)
    if "=" not in a.row:
        raise SystemExit("--row must be column=value")
    rk, rv = a.row.split("=", 1)
    if rk not in header:
        raise SystemExit(f"no such column {rk!r}; have {header}")
    ki = header.index(rk)
    hits = [i for i, r in enumerate(rows) if len(r) > ki and r[ki].strip() == rv.strip()]
    if not hits:
        raise SystemExit(f"no row with {rk}={rv}")
    if len(hits) > 1:
        print(f"!! {len(hits)} rows match {rk}={rv}; using the first", file=sys.stderr)
    i = hits[0]

    if a.get:
        if a.get not in header:
            raise SystemExit(f"no such column {a.get!r}")
        print(f"{rk}={rv}  {a.get} = {rows[i][header.index(a.get)]!r}")
        return 0

    if not a.set:
        print("nothing to do (pass --get or --set)")
        return 0
    if "=" not in a.set:
        raise SystemExit("--set must be column=value")
    sk, sv = a.set.split("=", 1)
    if sk not in header:
        raise SystemExit(f"no such column {sk!r}")
    si = header.index(sk)
    while len(rows[i]) <= si:
        rows[i].append("")
    old = rows[i][si]
    print(f"{rk}={rv}  {sk}: {old!r} -> {sv!r}")
    rows[i][si] = sv
    if a.dry:
        print("(dry run, not written)")
        return 0
    if not a.no_backup:
        bak = a.file + ".orig"
        if not os.path.exists(bak):
            shutil.copy2(a.file, bak)
            print(f"backup: {bak}")
        else:
            print(f"backup already exists: {bak}")
    save(a.file, header, rows, newline)
    print(f"written: {a.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
