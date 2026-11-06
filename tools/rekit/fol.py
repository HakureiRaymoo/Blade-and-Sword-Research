"""Reader for the `.fol` containers (`cj` / `mb` / `slr`).

Recovered from the engine:

* ``FUN_004e25e0`` (logged as ``InitGameFileProperty()``) opens
  ``<datadir><name>.fol`` for every name in the list built at startup
  (``cj`` / ``slr`` / ``mb``) and hands the handle to ``FUN_004e9de0``.
* ``FUN_004e9de0`` parses the directory::

      u32 count_raw
      count = count_raw & 0x7fffffff
      encrypted = (count_raw & 0x80000000) != 0

      count * 0x88 bytes   directory records   (0x88 = 136 bytes = 34 dwords)

      if encrypted:
          seek(filesize - (0x61 + count) * 4)      # 0x61 dwords of trailer follow
          read count * u32      per-record seed
          for i, j:  rec[i][j] -= j**3 * 9 + seed[i]        (mod 2**32)

* A record is looked up by the string at its start (``FUN_004e9c40``);
  ``+0x80`` is the payload offset and ``+0x84`` its size.
* Payload bytes come off the file at that offset and are decoded by
  ``FUN_004e9d30``::

      for i:  dword[i] -= 99 * i**2 + key      (mod 2**32)

    (only when the per-call flag is 1).

    py tools/rekit/fol.py list slr.fol
    py tools/rekit/fol.py extract slr.fol --out out/fol/slr
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"
REC = 0x88
REC_DWORDS = REC // 4
TRAILER_DWORDS = 0x61


class Fol:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data = self.path.read_bytes()
        (raw,) = struct.unpack_from("<I", self.data, 0)
        self.encrypted = bool(raw & 0x80000000)
        self.count = raw & 0x7FFFFFFF
        self.table_off = 4
        self.records: list[dict] = []
        self._parse()

    def _parse(self) -> None:
        need = self.table_off + self.count * REC
        if need > len(self.data):
            raise ValueError(f"{self.path.name}: directory runs past end")
        seeds: list[int] = [0] * self.count
        if self.encrypted:
            pos = len(self.data) - (TRAILER_DWORDS + self.count) * 4
            if pos < need:
                raise ValueError(f"{self.path.name}: seed block overlaps directory")
            seeds = list(struct.unpack_from(f"<{self.count}I", self.data, pos))
        for i in range(self.count):
            off = self.table_off + i * REC
            words = list(struct.unpack_from(f"<{REC_DWORDS}I", self.data, off))
            if self.encrypted:
                s = seeds[i]
                words = [(w - (j * j * j * 9 + s)) & 0xFFFFFFFF
                         for j, w in enumerate(words)]
            blob = struct.pack(f"<{REC_DWORDS}I", *words)
            name = blob.split(b"\0", 1)[0].decode("gbk", "replace")
            payload_off, payload_size = struct.unpack_from("<II", blob, 0x80)
            self.records.append({
                "index": i, "name": name, "offset": payload_off,
                "size": payload_size, "seed": seeds[i], "raw": blob,
            })

    def payload(self, index: int, key: int | None = None) -> bytes:
        """Read one resource and decode it like FUN_004e9d30.

        The engine decodes ``size >> 2`` dwords and leaves any 1..3 trailing
        bytes untouched, so mirror that here.
        """
        r = self.records[index]
        if not (0 <= r["offset"] <= len(self.data)):
            raise ValueError(f"record {index} offset {r['offset']:#x} out of range")
        blob = self.data[r["offset"]:r["offset"] + r["size"]]
        if key is None:
            return blob
        n = len(blob) // 4
        words = list(struct.unpack_from(f"<{n}I", blob, 0))
        words = [(w - (99 * i * i + key)) & 0xFFFFFFFF for i, w in enumerate(words)]
        return struct.pack(f"<{n}I", *words) + blob[n * 4:]

    @property
    def trailer(self) -> bytes:
        """The 0x61 dwords that follow the seed table at the end of the file."""
        return self.data[len(self.data) - TRAILER_DWORDS * 4:]


def _enc_dir(words: list[int], seed: int) -> bytes:
    enc = [(w + (j * j * j * 9 + seed)) & 0xFFFFFFFF for j, w in enumerate(words)]
    return struct.pack(f"<{len(enc)}I", *enc)


def _enc_payload(blob: bytes, seed: int) -> bytes:
    n = len(blob) // 4
    words = list(struct.unpack_from(f"<{n}I", blob, 0))
    words = [(w + (99 * i * i + seed)) & 0xFFFFFFFF for i, w in enumerate(words)]
    return struct.pack(f"<{n}I", *words) + blob[n * 4:]


def pack(root: str | Path, out: str | Path, source: Fol | None = None) -> dict:
    """Build a `.fol` from a directory tree.

    ``source`` (an already-opened original) supplies the seeds and the trailing
    0x61 dwords so an unmodified extract repacks byte-identically.  Without it,
    fresh random seeds are used and the trailer is zeroed.
    """
    root = Path(root)
    files = sorted(p for p in root.rglob("*") if p.is_file())
    names = [str(p.relative_to(root)).replace("/", "\\") for p in files]
    for n in names:
        if len(n.encode("gbk")) >= 0x80:
            raise ValueError(f"name too long for the 128-byte field: {n}")

    count = len(files)
    orig: dict[str, bytes] = {}
    if source is not None:
        if source.count != count:
            raise ValueError(f"source has {source.count} records, tree has {count}")
        seeds = [r["seed"] for r in source.records]
        trailer = source.trailer
        orig = {r["name"]: r["raw"] for r in source.records}
    else:
        import random
        rng = random.Random(0x5EED)
        seeds = [rng.getrandbits(32) for _ in range(count)]
        trailer = b"\0" * (TRAILER_DWORDS * 4)

    table_size = 4 + count * REC
    offsets = []
    pos = table_size
    blobs = []
    for p in files:
        blob = p.read_bytes()
        offsets.append((pos, len(blob)))
        blobs.append(blob)
        pos += len(blob)

    out_bytes = bytearray()
    out_bytes += struct.pack("<I", count | 0x80000000)
    for i, name in enumerate(names):
        # Records carry more than name/offset/size: the block before +0x80 holds
        # an author string and a few small fields.  Reuse the original record
        # bytes when we have them, so only offset/size ever change.
        base = bytearray(orig.get(name, bytes(REC)))
        if name not in orig:
            nb = name.encode("gbk")
            base[:len(nb)] = nb
        struct.pack_into("<II", base, 0x80, offsets[i][0], offsets[i][1])
        out_bytes += _enc_dir(list(struct.unpack_from(f"<{REC_DWORDS}I", base, 0)), seeds[i])
    for i, blob in enumerate(blobs):
        out_bytes += _enc_payload(blob, seeds[i])
    for s in seeds:
        out_bytes += struct.pack("<I", s)
    out_bytes += trailer

    Path(out).write_bytes(bytes(out_bytes))
    return {"count": count, "bytes": len(out_bytes), "out": str(out)}

    def close(self) -> None:
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("cmd", choices=["list", "extract", "info", "pack"])
    ap.add_argument("file")
    ap.add_argument("--out", default=r"D:\DSH WORK SPACE\Blade-and-Sword-Modernized\out\fol")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--from", dest="source", default="",
                    help="original .fol to reuse seeds/trailer from when packing")
    a = ap.parse_args(argv)

    if a.cmd == "pack":
        src = None
        if a.source:
            sp = a.source if os.path.isabs(a.source) else os.path.join(a.game, a.source)
            src = Fol(sp)
        info = pack(a.file, a.out, src)
        print(f"packed {info['count']} files -> {info['out']} ({info['bytes']:,} bytes)")
        return 0

    path = a.file if os.path.isabs(a.file) else os.path.join(a.game, a.file)
    fol = Fol(path)
    print(f"{fol.path.name}: {len(fol.data):,} bytes  count={fol.count}  "
          f"encrypted={fol.encrypted}")

    if a.cmd == "info":
        total = sum(r["size"] for r in fol.records)
        print(f"  payload total {total:,} bytes; first records:")
        for r in fol.records[: a.limit]:
            print(f"    {r['index']:>4}  {r['name']:<28} off={r['offset']:#010x} "
                  f"size={r['size']:>8} seed={r['seed']:#010x}")
        return 0

    if a.cmd == "list":
        for r in fol.records[: a.limit]:
            print(f"  {r['index']:>4}  {r['name']:<28} off={r['offset']:#010x} size={r['size']}")
        if len(fol.records) > a.limit:
            print(f"  ... {len(fol.records) - a.limit} more")
        return 0

    os.makedirs(a.out, exist_ok=True)
    for r in fol.records:
        # names look like "000\000_001.PLI" -- keep them as directories
        safe = r["name"].replace("\\", "/")
        safe = "/".join("".join(c if c.isalnum() or c in "-_. " else "_" for c in part)
                        for part in safe.split("/") if part)
        dst = os.path.join(a.out, safe or f"{r['index']:04d}.bin")
        os.makedirs(os.path.dirname(dst) or a.out, exist_ok=True)
        blob = fol.payload(r["index"], key=r["seed"]) if fol.encrypted else fol.payload(r["index"])
        open(dst, "wb").write(blob)
    print(f"  extracted {len(fol.records)} files -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
