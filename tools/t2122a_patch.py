#!/usr/bin/env python3
"""Patch a Titanium T2122A firmware image so the vendor web UI accepts it.

The vendor updater (image_check_tc in libcfg_clisvc.so) reads a 256-byte HDR2
header and validates:

  * magic  "HDR2"          @ 0x00
  * length                 @ 0x08   (little endian, includes the header)
  * JAMCRC (~crc32)        @ 0x0c   (covers payload from 0x100 to length)
  * model                  @ 0x88   (8 bytes; on the Excitel build it must be
  *                                 T2122EUZ or T2122ELZ)
  * upgrade gate           @ 0x80   (u32; 0 blocks, 1 allows)

It does NOT cover the header in the CRC, so changing version/model/gate does
not require recomputing anything. The payload is left byte-for-byte intact.

Usage:
  ./t2122a_patch.py --check tclinux.bin
  ./t2122a_patch.py -o tclinux-unlocked.bin tclinux.bin
  ./t2122a_patch.py --preset excitel -o out.bin tclinux.bin
  ./t2122a_patch.py --preset airtel  -o out.bin tclinux.bin
  ./t2122a_patch.py --model T2122ELZ --version T2122-V1.33EXU -o out.bin in.bin
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import zlib

HDR_SIZE = 0x100
OFF_MAGIC = 0x00
OFF_LENGTH = 0x08
OFF_CRC = 0x0C
OFF_VERSION = 0x10
OFF_GATE = 0x80
OFF_MODEL = 0x88
VERSION_FIELD = 32
MODEL_FIELD = 16

KNOWN_MODELS = ("T2122EUZ", "T2122ELZ")
DEFAULT_VERSION = "T2122-V1.33EXU"
PRESETS = {
    # Excitel stock images already carry T2122EUZ; the generic V1.30 retail
    # image carries just "T2122", which the vendor updater rejects.
    "excitel": "T2122EUZ",
    # The Excitel build also accepts T2122ELZ. There is no evidence that ELZ is
    # the Airtel model string; this preset is an unverified guess. Patch an
    # Airtel dump and read its own model/validator before relying on it.
    "airtel": "T2122ELZ",
}


def jamcrc(payload: bytes) -> int:
    return (~zlib.crc32(payload)) & 0xFFFFFFFF


def cstring(buf: bytes) -> str:
    return buf.split(b"\0", 1)[0].decode("ascii", "replace")


class Image:
    def __init__(self, data: bytearray, path: str):
        self.data = data
        self.path = path

    @classmethod
    def load(cls, path: str) -> "Image":
        with open(path, "rb") as f:
            data = bytearray(f.read())
        return cls(data, path)

    @property
    def magic(self) -> bytes:
        return bytes(self.data[OFF_MAGIC:OFF_MAGIC + 4])

    @property
    def declared_length(self) -> int:
        return struct.unpack_from("<I", self.data, OFF_LENGTH)[0]

    @property
    def stored_crc(self) -> int:
        return struct.unpack_from("<I", self.data, OFF_CRC)[0]

    @property
    def version(self) -> str:
        return cstring(bytes(self.data[OFF_VERSION:OFF_VERSION + VERSION_FIELD]))

    @property
    def gate(self) -> int:
        return self.data[OFF_GATE]

    @property
    def model(self) -> str:
        return cstring(bytes(self.data[OFF_MODEL:OFF_MODEL + MODEL_FIELD]))

    def computed_crc(self) -> int:
        end = self.declared_length
        return jamcrc(bytes(self.data[HDR_SIZE:end]))

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.magic != b"HDR2":
            errors.append(f"bad magic {self.magic!r} (expected b'HDR2')")
        if self.declared_length < HDR_SIZE or self.declared_length > len(self.data):
            errors.append(
                f"declared length {self.declared_length} outside "
                f"{HDR_SIZE}..{len(self.data)}"
            )
        if not errors and self.stored_crc != self.computed_crc():
            errors.append(
                f"JAMCRC mismatch: header says 0x{self.stored_crc:08x}, "
                f"payload is 0x{self.computed_crc():08x}"
            )
        return errors

    def set_version(self, version: str) -> None:
        raw = version.encode("ascii")
        if len(raw) > VERSION_FIELD:
            raise ValueError(f"version is {len(raw)} bytes, max {VERSION_FIELD}")
        self.data[OFF_VERSION:OFF_VERSION + VERSION_FIELD] = raw.ljust(
            VERSION_FIELD, b"\0"
        )

    def set_model(self, model: str) -> None:
        raw = model.encode("ascii")
        if len(raw) > MODEL_FIELD:
            raise ValueError(f"model is {len(raw)} bytes, max {MODEL_FIELD}")
        self.data[OFF_MODEL:OFF_MODEL + MODEL_FIELD] = raw.ljust(MODEL_FIELD, b"\0")

    def set_gate(self, value: int) -> None:
        struct.pack_into("<I", self.data, OFF_GATE, value & 0xFFFFFFFF)

    def write(self, path: str, keep_size: bool = False) -> None:
        out = path
        if os.path.abspath(out) == os.path.abspath(self.path):
            out = self.path + ".patched"
        data = self.data
        if not keep_size and len(data) > self.declared_length:
            # A full mtd dump has 0xff padding after the declared image. The
            # web updater only needs the declared image; drop the padding so the
            # upload size matches what the header says.
            print(f"trimming {len(data) - self.declared_length} bytes of mtd padding")
            data = data[:self.declared_length]
        with open(out, "wb") as f:
            f.write(data)
        print(f"wrote {out} ({len(data)} bytes)")


def resolve_model(img: Image, requested: str) -> str:
    if requested != "auto":
        return requested
    if img.model in KNOWN_MODELS:
        return img.model
    return PRESETS["excitel"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Patch a Titanium T2122A HDR2 firmware image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("image", help="input HDR2 image (do not use an OpenWrt .trx)")
    ap.add_argument("-o", "--output", help="output image (default: <input>.unlocked)")
    ap.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="set the 0x88 model ('airtel' is an unverified T2122ELZ guess)",
    )
    ap.add_argument(
        "--model",
        default=None,
        help="model string at 0x88, or 'auto' (keep EUZ/ELZ, else EUZ)",
    )
    ap.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help=f"version string at 0x10 (default: {DEFAULT_VERSION})",
    )
    ap.add_argument(
        "--gate",
        type=lambda s: int(s, 0),
        default=1,
        help="u32 at 0x80 (default: 1 = allow upgrade)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="only validate the input, do not write an image",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="write even if the input CRC/length does not validate",
    )
    ap.add_argument(
        "--keep-size",
        action="store_true",
        help="keep trailing mtd padding instead of trimming to the declared length",
    )
    args = ap.parse_args(argv)

    try:
        img = Image.load(args.image)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if img.magic != b"HDR2":
        print(
            f"error: {args.image} is not an HDR2 image (magic {img.magic!r}).\n"
            "       OpenWrt .trx images are flashed with mtd, not the vendor UI.",
            file=sys.stderr,
        )
        return 2

    errors = img.validate()
    print(f"input:   {args.image}")
    print(f"  length {img.declared_length} / file {len(img.data)}")
    print(f"  crc    0x{img.stored_crc:08x}")
    print(f"  version {img.version!r}")
    print(f"  gate   0x{img.gate:02x}")
    print(f"  model  {img.model!r}")
    if errors:
        for err in errors:
            print(f"  BAD: {err}")
        if not args.force:
            print("refusing to patch a damaged image (use --force to override)",
                  file=sys.stderr)
            return 1
    else:
        print("  header and payload CRC are valid")

    if args.check:
        return 0 if not errors else 1

    model = args.preset and PRESETS[args.preset] or args.model or "auto"
    model = resolve_model(img, model)
    if args.preset == "airtel":
        print(
            "warning: --preset airtel uses T2122ELZ. No Airtel image was "
            "available to confirm that string; verify it against your own "
            "dump/validator (see docs/VARIANTS.md)."
        )
    if len(model.encode("ascii")) > MODEL_FIELD:
        print(f"error: model {model!r} does not fit in {MODEL_FIELD} bytes",
              file=sys.stderr)
        return 2

    original_model = img.model
    img.set_version(args.version)
    img.set_model(model)
    img.set_gate(args.gate)

    # Header-only edits must never invalidate the payload CRC.
    after = img.validate()
    if after and not args.force:
        print("internal error: patch changed the CRC/length", file=sys.stderr)
        return 3

    out = args.output or (os.path.splitext(args.image)[0] + ".unlocked.bin")
    print(
        f"patch:   version {args.version!r}, gate 0x{args.gate:02x}, "
        f"model {original_model!r} -> {model!r}"
    )
    img.write(out, args.keep_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
