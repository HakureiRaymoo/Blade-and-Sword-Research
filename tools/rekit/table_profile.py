"""Profile every column of a GBK TSV table so the unknowns can be triaged.

For each column it reports the value kind (int / float / list / text), the number
of distinct values, the range, and a couple of examples.  Columns that are empty
for every row are unused; columns with tiny distinct counts look like enums;
columns with a wide numeric spread look like tunable parameters.

    py tools/rekit/table_profile.py --file <Role.txt> --out docs/04-role-columns.md
"""
from __future__ import annotations

import argparse
import collections
import os
import re

ENCODING = "gbk"
LIST_SEP = re.compile(r"[*]")


def classify(values: list[str]) -> tuple[str, str]:
    vals = [v for v in values if v.strip() != ""]
    if not vals:
        return "empty", "全部为空"
    numeric = sum(1 for v in vals if re.fullmatch(r"-?\d+", v.strip()))
    if numeric == len(vals):
        ints = [int(v) for v in vals]
        return "int", f"{min(ints)} .. {max(ints)}"
    if all(re.fullmatch(r"-?\d+", p) for v in vals for p in LIST_SEP.split(v) if p.strip()):
        return "int-list", "星号分隔的整数序列"
    floats = sum(1 for v in vals if re.fullmatch(r"-?\d*\.\d+", v.strip()))
    if floats > 0:
        return "float", "含小数"
    return "text", "文本"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--key", default="", help="column used to label examples")
    a = ap.parse_args(argv)

    raw = open(a.file, "rb").read().decode(ENCODING, "replace")
    lines = [ln for ln in raw.replace("\r\n", "\n").split("\n") if ln]
    header = lines[0].split("\t")
    rows = [ln.split("\t") for ln in lines[1:]]
    rows = [r for r in rows if len(r) >= len(header) - 4]
    n = len(rows)
    print(f"{os.path.basename(a.file)}: {n} rows x {len(header)} columns")

    out = []
    out.append(f"# `{os.path.basename(a.file)}` 列画像\n")
    out.append(f"- 文件：`{a.file}`")
    out.append(f"- 行数：{n}（不含表头）")
    out.append(f"- 列数：{len(header)}\n")
    out.append("| # | 列名 | 类型 | 不同值 | 范围 / 说明 | 例子 |")
    out.append("| --- | --- | --- | --- | --- | --- |")

    for i, name in enumerate(header):
        values = [r[i] if i < len(r) else "" for r in rows]
        kind, note = classify(values)
        distinct = collections.Counter(v for v in values if v.strip())
        examples = ", ".join(f"`{v}`" for v, _ in distinct.most_common(3))
        out.append(f"| {i} | {name} | {kind} | {len(distinct)} | {note} | {examples[:70]} |")
        print(f"  [{i:2}] {name:<12} {kind:<9} distinct={len(distinct):<4} {note}")

    text = "\n".join(out) + "\n"
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
