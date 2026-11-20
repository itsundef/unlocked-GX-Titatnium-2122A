# The T2122A firmware header and the universal patcher

The vendor web updater accepts a single file: an `HDR2` image containing a
kernel and a SquashFS rootfs. It checks a 256-byte header, then writes the
payload to the inactive bank. The payload CRC does **not** cover the header, so
the unlock is a pure header edit.

## 1. Header layout

| Offset | Size | Meaning | Notes |
|---:|---:|---|---|
| `0x00` | 4 | magic | ASCII `HDR2` |
| `0x08` | 4 | total length | little-endian, includes the 256-byte header |
| `0x0c` | 4 | JAMCRC | `~crc32(payload[0x100:length])`, little-endian |
| `0x10` | 32 | version | e.g. `T2122-V1.33EXU`, NUL-padded |
| `0x50` | 4 | kernel length | bytes |
| `0x54` | 4 | rootfs length | bytes |
| `0x7c` | 4 | kernel load address | normally `0x80002000` |
| `0x80` | 4 | upgrade gate | little-endian u32; must be `1`, `0` in untouched retail images |
| `0x88` | 16 | model / variant | 8-byte compare; Excitel accepts `T2122EUZ` or `T2122ELZ` |

There is **no `EULX` string** in these images. On Excitel the version suffix is
`EXU` (`T2122-V1.30`, `T2122-V1.32EXU`, `T2122-V1.33EXU`) and the 8-byte model
strings are `T2122EUZ` / `T2122ELZ`. Public Airtel builds use the `AE` suffix
(`T2122-V1.17AE`, `T2122-V1.26AE`); their model string is not confirmed. The
confusion is understandable; if you remember "EULX", it was almost certainly one
of those.

The stock Excitel V1.32EXU header already contains `T2122EUZ` but has gate `0`.
The generic/retail V1.30 image contains just `T2122` and gate `0`, which is why
it is rejected as-is.

## 2. What the updater actually checks

`image_check_tc()` lives in `/lib/libcfg_clisvc.so`. In the installed V1.32EXU
build it does roughly:

```c
read_header(path, hdr, 256);
if (hdr->magic != "HDR2" || hdr->length > file_size) fail;
if (hdr->jamcrc != ~crc32(file + 0x100, hdr->length - 0x100)) fail;

/* model gate */
if (cfg_get("root.Sys.Entry", "CUSTOMER") < 0) {
    if (memcmp(hdr->model, "T2122EUZ", 8) != 0 &&
        memcmp(hdr->model, "T2122ELZ", 8) != 0)
        fail("Wrong file formate! trx_trunc_version=%s");
}
```

Two consequences:

- Patching the header (version/model/gate) cannot invalidate the payload CRC.
- The validator skips the model check if `root.Sys.Entry.CUSTOMER` exists in
  the live romfile. That is a useful escape hatch, but editing the romfile is
  riskier than patching a header; use it only if your variant's validator
  insists on a model string you cannot reproduce.

The updater also reads `root.System.Entry.UpgradeSWVersion` from the live config
and parses the header version next to it. The tested, accepted value is
`T2122-V1.33EXU`; keep it. The `0x80` gate is checked as a 32-bit word and must
be `1`; the tested working image sets it, so leave it set. If your build rejects
a header that passes the model and CRC checks, compare your stock version string
and the updater's exact error before changing the version field.

## 3. Patch your own image

Always prefer your own stock image. Dump it first (see
[RECOVERY.md](RECOVERY.md)), then:

```sh
cd latestt2122a

# inspect only
python3 tools/t2122a_patch.py --check /path/to/your-stock.bin

# Excitel / generic image -> T2122EUZ
python3 tools/t2122a_patch.py --preset excitel \
    -o /tmp/tclinux-unlocked.bin /path/to/your-stock.bin

# Airtel guess: ELZ model with an AE-format version (both untested)
python3 tools/t2122a_patch.py --model T2122ELZ --version T2122-V1.33AE \
    -o /tmp/tclinux-unlocked-elz.bin /path/to/your-stock.bin
```

The Airtel model string is not confirmed. See [VARIANTS.md](VARIANTS.md)
before using that preset; if you can read your own validator, patch the exact
string it accepts.

The patcher:

- refuses anything that is not `HDR2` (an OpenWrt `.trx` is **not** a vendor
  image; flash that with `mtd`, not the web UI),
- validates the declared length and the payload JAMCRC,
- writes only `0x10..0x2f`, `0x80`, and `0x88..0x97`,
- re-validates the CRC after patching,
- trims a full mtd dump to the declared image length (use `--keep-size` to keep
  the trailing `0xff` padding),
- supports `--model auto` (keep an existing `EUZ`/`ELZ`, otherwise use `EUZ`),
  `--model <string>`, `--version <string>`, `--gate <n>`, and `--force`.

`--preset excitel` on the retail V1.30 image reproduces the exact image that was
flashed successfully on the development unit (byte-for-byte). That image's
SHA256 is:

```
72e946c47d542a89df1acb38310f84dcbd3b44b883f204ab6865b72189845d07
```

## 4. Included images

| File | Header | Status |
|---|---|---|
| `firmware/tclinux-T2122-V1.33EXU-unlocked.bin` | `V1.33EXU`, gate 1, `T2122EUZ` | Tested on Excitel |
| `firmware/tclinux-T2122-V1.33EXU-ELZ-untested.bin` | `V1.33EXU`, gate 1, `T2122ELZ` | Untested; same payload, alternate model string. Not confirmed to be an Airtel image. |

SHA256:

```
72e946c47d542a89df1acb38310f84dcbd3b44b883f204ab6865b72189845d07  EUZ (tested)
e8732ade66582451e462adc0fd8b88614862957b75536652c873400a82e1abad  ELZ (untested)
```

Both are the generic V1.30 vendor build with a patched header. The running
system will report `V1.33EXU`; the code underneath is V1.30. The stock
configuration partition is not touched by the vendor updater, so WAN settings
usually survive.

If you have your own dump, patch that instead. It will match your ISP's
provisioning and any hardware revision differences.

## 5. Web upgrade

1. Boot the **stock** firmware (the main bank).
2. Note the current version and, if you have shell, the boot flag (`0x30`).
3. Open the upgrade page:
   - Excitel: `http://192.168.1.1/cgi-bin/upgrade.asp`
   - Some builds show it under **Manage → Upgrade**.
4. Upload the patched image. The filename must contain `tclinux` (rename your
   copy if needed). Keep the router powered.
5. The updater writes the **inactive** bank, flips the boot flag, and reboots.
   Your stock firmware remains on the other bank.
6. After reboot, the web UI reports the patched version. The stock WAN config is
   still in the config partition; check it before connecting the fibre.

If the upload is rejected, the message usually tells you which check failed.
`Wrong file formate` = model string; an immediate generic failure = CRC/length
or gate. Do not retry blindly; inspect the header with `--check`.

## 6. Direct flash (advanced)

If the web UI is unavailable but you have a root shell, write the patched image
to the inactive bank with the vendor `mtd` tool. Check `imginfo` or the boot
flag first, then use the partition name that is **not** currently booted. The
command used on the development unit (booted from main, writing the slave bank):

```sh
/userfs/bin/mtd -f write /tmp/tclinux-unlocked.bin 18250464 0 tclinux_slave
```

Verify the size and header first; a wrong length or the wrong partition name
turns a recoverable mistake into a UART job. Partition names and offsets are in
[RECOVERY.md](RECOVERY.md).

Never flash a vendor `HDR2` image with `mtdwrite` to a partition that is
currently mounted; use the vendor updater or boot from the other bank.
