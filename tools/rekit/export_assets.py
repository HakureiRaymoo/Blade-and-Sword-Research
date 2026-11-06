"""Batch exporter for Blade & Fairy resource libraries.

Walks a ``.Lib`` archive, decodes every ``lep`` picture (and, for sprite
entries, every frame of the enclosing bundle), writes PNGs plus an index.

Usage:
    py tools/rekit/export_assets.py --game "<install dir>" --out out/assets \
        --libs ResJM Spr ResPlayer1 --fmt rgb565

Library names may be given without the ``.Lib`` suffix; the language suffix
(``.chs``) is tried automatically.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lep import LepImage  # noqa: E402
from leylib import LeyiLib  # noqa: E402


def split_bundle(data: bytes) -> list[bytes] | None:
    """Split a sprite entry into frames.

    Layout:  u32 count | u32 offset[count] | frames...
    Frame i spans [offset[i], offset[i+1]) and is itself a `lep` picture.
    """
    if len(data) < 8:
        return None
    (n,) = struct.unpack_from("<I", data, 0)
    if n == 0 or n > 20000 or 4 + 4 * n > len(data):
        return None
    (first,) = struct.unpack_from("<I", data, 4)
    if first != 4 + 4 * n:
        return None
    offsets = list(struct.unpack_from(f"<{n}I", data, 4))
    if any(b <= a for a, b in zip(offsets, offsets[1:])) or offsets[-1] > len(data):
        return None
    parts = []
    for i, off in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < n else len(data)
        parts.append(data[off:end])
    if not all(p[:4] == b"lep\0" for p in parts):
        return None
    return parts


def resolve(game: Path, name: str) -> Path | None:
    zy = game / "zy"
    for cand in (name, f"{name}.Lib.chs", f"{name}.Lib", f"{name}.lib"):
        p = zy / cand
        if p.exists():
            return p
    return None


def export_entry(lib: LeyiLib, index: int, dst: Path, fmt: str) -> dict:
    data = lib.read(index)
    info: dict = {"entry": index, "bytes": len(data), "frames": [], "kind": None}

    frames = split_bundle(data)
    if frames:
        info["kind"] = "bundle"
        targets = frames
    elif data[:4] == b"lep\0":
        info["kind"] = "lep"
        targets = [data]
    else:
        info["kind"] = "raw"
        (dst / f"{index:05d}.bin").write_bytes(data)
        return info

    for fi, payload in enumerate(targets):
        image = LepImage.parse(payload)
        w, h, buf = image.to_rgba(fmt)
        from PIL import Image  # imported lazily so the rest works without Pillow
        img = Image.frombytes("RGBA", (w, h), bytes(buf))
        name = f"{index:05d}.png" if len(targets) == 1 else f"{index:05d}_{fi:03d}.png"
        img.save(dst / name)
        info["frames"].append({"file": name, "w": w, "h": h})
    return info


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, help="game install directory")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--libs", nargs="+", required=True, help="library names, e.g. ResJM Spr")
    ap.add_argument("--fmt", default="rgb565", choices=["rgb565", "bgr565", "argb1555"])
    ap.add_argument("--limit", type=int, default=0, help="max entries per library (0 = all)")
    args = ap.parse_args(argv)

    game = Path(args.game)
    out = Path(args.out)
    manifest = []
    for name in args.libs:
        path = resolve(game, name)
        if path is None:
            print(f"!! library not found: {name}", file=sys.stderr)
            continue
        dst = out / path.stem.split(".")[0]
        dst.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        with LeyiLib(path) as lib:
            limit = args.limit or lib.count
            ok = fail = 0
            for i in range(min(limit, lib.count)):
                try:
                    manifest.append({"lib": path.name, "dir": str(dst.relative_to(out)), **export_entry(lib, i, dst, args.fmt)})
                    ok += 1
                except Exception as exc:  # noqa: BLE001 - report and continue
                    fail += 1
                    manifest.append({"lib": path.name, "entry": i, "error": repr(exc)})
        dt = time.time() - t0
        print(f"{path.name}: {ok} ok, {fail} failed in {dt:.1f}s -> {dst}")

    (out / "index.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"index written: {out / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
