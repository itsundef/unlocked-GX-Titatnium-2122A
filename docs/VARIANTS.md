# Variants: Excitel, Airtel, and everything else

The T2122A hardware is the same across the variants seen so far: EcoNet EN7528,
256 MiB NAND, MT7603 + MT7663 Wi-Fi, two GbE ports, one FXS port. The difference
is the ISP firmware build and the `romfile` configuration partition.

## What is verified

| Variant | Stock version seen | Header model | Status |
|---|---|---|---|
| Excitel | `T2122-V1.32EXU` | `T2122EUZ` | Unlock tested end-to-end |
| Airtel | `T2122-V1.17AE`, `T2122-V1.26AE` | unknown; do not assume `ELZ` | Method applies; **not tested** |
| Other | unknown | read it from your own image | Use the patcher, do not guess |

The Airtel versions are from public owner reports (India Broadband Forum,
2025), not from a unit in hand. The version suffix is `AE`, not `EXU`:

- `T2122-V1.17AE` (Feb 2025)
- `T2122-V1.26AE` (Oct 2025)

The vendor validator in the Excitel V1.32EXU build accepts exactly two 8-byte
model strings at header `0x88`: `T2122EUZ` and `T2122ELZ`. `ELZ` is the only
alternate string known to be accepted by that validator, but there is **no
evidence that it is the Airtel model**. Treat the Airtel preset as a guess until
an Airtel image or validator dump confirms it.

## Find the model strings your validator accepts

If you have any shell (Samba magic script, vendor telnet, UART), copy the
validator library off the device and inspect it on your host:

```sh
# on the router, if wget/HTTP is available, or over the Samba share:
cp /lib/libcfg_clisvc.so /tmp/
# then copy /tmp/libcfg_clisvc.so to your host

strings -a libcfg_clisvc.so | grep -E '^T2122[A-Z]{3}$'
```

You will see the accepted strings. On the Excitel build:

```
T2122EUZ
T2122ELZ
```

If your build accepts a different string, patch to **that exact 8-byte string**:

```sh
python3 tools/t2122a_patch.py --model YOURSTR1 \
    -o /tmp/unlocked.bin /path/to/your-stock.bin
```

Do not invent a string. The comparison is an 8-byte `memcmp`; a wrong value is
rejected exactly like no patch at all.

If you cannot get a shell yet, run `--check` on your own stock image. The
`model` field in the image is what your vendor built, but it is not necessarily
the only string the validator accepts.

## Airtel notes

- Airtel GPON on the EN7528 family commonly uses **VLAN 100 PPPoE** on the WAN.
  That is a configuration detail, not a firmware-lock detail. The vendor
  firmware supports it; the stock `romfile` usually already has the right
  profile.
- The web UI and default logins differ between ISP builds. Do not assume the
  Excitel `excitel` / `exc@123` login works.
- The Airtel version string uses the `AE` suffix. The patcher default
  (`T2122-V1.33EXU`) is the value tested on Excitel; if the Airtel updater
  rejects it, try a value in the Airtel format at or above your installed
  version, for example:
  ```sh
  python3 tools/t2122a_patch.py --model T2122ELZ \
      --version T2122-V1.33AE -o /tmp/airtel-unlocked.bin stock.bin
  ```
  This combination is **untested**. The header version and model are the only
  things that change; the payload is still the image you supplied.
- Prefer patching an Airtel dump over flashing the included Excitel-based
  image. The payload is generic, but your ISP's provisioning lives in the config
  partition and is easier to keep than to recreate.
- The included V1.30 rootfs has no Excitel- or Airtel-specific branding or
  profile strings; the ISP profile lives in the `romfile` partition. That is why
  the same payload can be offered with either model header — but it does not
  prove that an Airtel validator will accept it.

Public version reports:
[India Broadband Forum, Airtel Titanium-2122A](https://broadband.forum/threads/airtel-titanium-2122a-upgraded-cant-create-5ghz-ssid.236018/).

## Other variants

1. Identify the stock version in the web UI (**Status → Device Information**) or
   in the image header (`--check`).
2. Get root with [SAMBA-TELNET.md](SAMBA-TELNET.md). If Samba is missing, use
   the hidden upgrade page with a patched image, or UART.
3. Extract the model strings from `/lib/libcfg_clisvc.so` as above.
4. Patch your own stock image and flash it through the vendor UI.
5. If the UI still refuses, write the patched image to the inactive bank with
   the vendor `mtd` tool (see [RECOVERY.md](RECOVERY.md)).

## The `CUSTOMER` bypass

The V1.32EXU validator skips the model `memcmp` when the live romfile contains
`root.Sys.Entry.CUSTOMER`. That means a correctly signed/CRC'd image with the
original `T2122` model can pass on some builds. This is reverse-engineered, not
tested as an unlock path, and editing the romfile is riskier than patching a
header. Treat it as a last resort and keep a config dump.

## Do not cross-flash blindly

- An OpenWrt `.trx` is not a vendor `HDR2` image. The web UI will reject it; do
  not rename it and retry.
- A vendor image for a different EN7528 board (JCOW407, etc.) is not compatible
  just because the SoC matches. The T2122A has its own DTS, PHY map and flash
  layout.
- The config partition is per-ISP. A firmware swap preserves it; a full flash
  or erase does not.
