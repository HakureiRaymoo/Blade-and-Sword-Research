"""Reader for the "leyiLib2.0" resource archives used by Blade & Fairy.

Format (verified against every *.lib shipped with 上古传说):

    offset 0x00   10 bytes   b"leyiLib2.0"
    offset 0x0A    6 bytes   padding: 00 cc cc cc cc cc
    offset 0x10    4 bytes   uint32 little-endian entry count N
    offset 0x14    0xEC       reserved, zero-filled
    offset 0x100   8*N       entry table, N x (uint32 offset, uint32 size)
    offset 0x100+8N          raw entry payloads, laid out back-to-back

The table is strictly contiguous and the first payload starts exactly at
0x100 + 8N, so the header size is derived from N. Entries are addressed by
index only -- the archives carry no filenames. Name<->index mapping lives in
the game's data tables (e.g. PropMdl.txt / Role.txt) and in code.

CLI:
    py tools/rekit/leylib.py info  <archive>...
    py tools/rekit/leylib.py list  <archive> [--limit N]
    py tools/rekit/leylib.py extract <archive> <outdir> [--start N] [--count N]
"""
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"leyiLib2.0"
HEADER_SIZE = 0x100
TABLE_OFFSET = 0x100


@dataclass(frozen=True)
class Entry:
    index: int
    offset: int
    size: int

    @property
    def end(self) -> int:
        return self.offset + self.size


class LeyiLib:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._fh = self.path.open("rb")
        head = self._fh.read(0x14)
        if head[: len(MAGIC)] != MAGIC:
            raise ValueError(f"{self.path.name}: not a leyiLib2.0 archive (magic={head[:11]!r})")
        (self.count,) = struct.unpack_from("<I", head, 0x10)
        self._fh.seek(TABLE_OFFSET)
        self._table = self._fh.read(self.count * 8)
        if len(self._table) != self.count * 8:
            raise ValueError(f"{self.path.name}: truncated entry table")

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "LeyiLib":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- queries ---------------------------------------------------------
    @property
    def header_size(self) -> int:
        return TABLE_OFFSET + self.count * 8

    def entries(self):
        off = 0
        for i in range(self.count):
            start, size = struct.unpack_from("<II", self._table, off)
            off += 8
            yield Entry(i, start, size)

    def entry(self, index: int) -> Entry:
        if not 0 <= index < self.count:
            raise IndexError(index)
        start, size = struct.unpack_from("<II", self._table, index * 8)
        return Entry(index, start, size)

    def verify(self) -> list[str]:
        """Return a list of structural problems (empty list == healthy)."""
        problems: list[str] = []
        expected = self.header_size
        total = 0
        for e in self.entries():
            if e.offset != expected:
                problems.append(f"entry {e.index}: offset {e.offset:#x} != expected {expected:#x}")
            expected = e.end
            total += e.size
        file_size = self.path.stat().st_size
        if expected != file_size:
            problems.append(f"payload ends at {expected:#x} but file is {file_size:#x}")
        return problems

    def read(self, index: int) -> bytes:
        e = self.entry(index)
        self._fh.seek(e.offset)
        data = self._fh.read(e.size)
        if len(data) != e.size:
            raise IOError(f"{self.path.name}: short read on entry {index}")
        return data

    def iter_data(self):
        for e in self.entries():
            self._fh.seek(e.offset)
            yield e, self._fh.read(e.size)


# ---------------------------------------------------------------------------
# payload sniffing -- lets extraction produce meaningful extensions
# ---------------------------------------------------------------------------
_MAGICS: list[tuple[bytes, str]] = [
    (b"BM", ".bmp"),
    (b"\x89PNG", ".png"),
    (b"DDS ", ".dds"),
    (b"RIFF", ".wav"),
    (b"OggS", ".ogg"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"ID3", ".mp3"),
    (b"GIF8", ".gif"),
    (b"leyiLib2.0", ".lib"),
]


def guess_ext(data: bytes) -> str:
    for magic, ext in _MAGICS:
        if data.startswith(magic):
            return ext
    return ".bin"


def _cmd_info(args) -> int:
    rc = 0
    for p in args.archives:
        try:
            with LeyiLib(p) as lib:
                problems = lib.verify()
                sizes = [e.size for e in lib.entries()]
                print(f"{Path(p).name:24s} entries={lib.count:<6} "
                      f"payload={sum(sizes):,} file={Path(p).stat().st_size:,} "
                      f"min={min(sizes) if sizes else 0} max={max(sizes) if sizes else 0}")
                for msg in problems[:5]:
                    print(f"    !! {msg}")
                if problems:
                    rc = 1
        except (ValueError, OSError) as exc:
            print(f"{Path(p).name}: {exc}", file=sys.stderr)
            rc = 1
    return rc


def _cmd_list(args) -> int:
    with LeyiLib(args.archive) as lib:
        for e in lib.entries():
            if e.index >= args.limit:
                break
            data = lib.read(e.index)
            print(f"{e.index:6d} off={e.offset:#010x} size={e.size:>9,} {guess_ext(data):5s} {data[:8].hex(' ')}")
    return 0


def _cmd_extract(args) -> int:
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    with LeyiLib(args.archive) as lib:
        stop = args.start + args.count if args.count else lib.count
        written = 0
        for e in lib.entries():
            if e.index < args.start or e.index >= stop:
                continue
            data = lib.read(e.index)
            dst = out / f"{e.index:05d}{guess_ext(data)}"
            dst.write_bytes(data)
            written += 1
    print(f"extracted {written} entries -> {out}")
    return 0


def _cmd_pack(args) -> int:
    """Rebuild a `leyiLib2.0` archive from a directory of numbered entries.

    Only used for modding: extract a library with ``extract``, replace one or
    more ``NNNNN.bin`` files, then pack it back.  Entry order and count are
    taken from the file names, so the directory must cover 0..N-1 with no gaps.
    """
    src = Path(args.dir)
    entries: dict[int, Path] = {}
    for p in src.iterdir():
        if not p.is_file():
            continue
        stem = p.stem
        if stem.isdigit():
            entries[int(stem)] = p
    if not entries:
        print(f"{src}: no numbered files found", file=sys.stderr)
        return 1
    n = max(entries) + 1
    missing = [i for i in range(n) if i not in entries]
    if missing:
        print(f"{src}: missing entries {missing[:10]}", file=sys.stderr)
        return 1

    payloads = [entries[i].read_bytes() for i in range(n)]
    header_size = TABLE_OFFSET + n * 8
    table = bytearray()
    off = header_size
    for data in payloads:
        table += struct.pack("<II", off, len(data))
        off += len(data)

    out = Path(args.out)
    with out.open("wb") as fh:
        head = bytearray(TABLE_OFFSET)
        head[: len(MAGIC)] = MAGIC
        # the six bytes after the magic are 0xCC in every shipped library
        head[len(MAGIC):0x10] = b"\x00" + b"\xcc" * 5
        struct.pack_into("<I", head, 0x10, n)
        fh.write(head)
        fh.write(table)
        for data in payloads:
            fh.write(data)
    print(f"packed {n} entries -> {out} ({out.stat().st_size:,} bytes)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="validate archives and print summary")
    p_info.add_argument("archives", nargs="+")
    p_info.set_defaults(func=_cmd_info)

    p_list = sub.add_parser("list", help="list entries with sniffed type")
    p_list.add_argument("archive")
    p_list.add_argument("--limit", type=int, default=40)
    p_list.set_defaults(func=_cmd_list)

    p_ext = sub.add_parser("extract", help="extract entries to a directory")
    p_ext.add_argument("archive")
    p_ext.add_argument("outdir")
    p_ext.add_argument("--start", type=int, default=0)
    p_ext.add_argument("--count", type=int, default=0, help="0 = to the end")
    p_ext.set_defaults(func=_cmd_extract)

    p_pack = sub.add_parser("pack", help="rebuild an archive from numbered entries")
    p_pack.add_argument("dir")
    p_pack.add_argument("out")
    p_pack.set_defaults(func=_cmd_pack)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
