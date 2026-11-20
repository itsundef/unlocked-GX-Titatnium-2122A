# Titanium T2122A — unlock and liberation kit

A community kit for the **Titanium-2122A** GPON ONT (EcoNet EN7528, 256 MiB
NAND, MT7603 + MT7663 Wi-Fi, 2×GbE, 1×FXS). It gives you root, unlocks the
vendor firmware, and optionally puts OpenWrt on the second flash bank.

Developed and tested on an **Excitel** unit running stock `T2122-V1.32EXU`.
The same method should work on Airtel and other T2122A variants; see
[VARIANTS.md](docs/VARIANTS.md) for what is verified and what is not.

> **Read this first.** You can brick the router. Keep the stock bank, dump the
> flash before you start, and do not publish your `romfile` or full-flash dump:
> it contains your MAC, serial, Wi-Fi keys and ISP credentials. No warranty.

---

## Choose a path

| I want to... | Path | Risk |
|---|---|---|
| Get a root shell without flashing anything | [Samba magic script](docs/SAMBA-TELNET.md) | Low; one-shot, no firmware change |
| Run unlocked vendor firmware with telnet | [Patched HDR2 image](docs/FIRMWARE.md) | Medium; writes the inactive bank |
| Own the whole stack (Wi-Fi, SSH, LuCI) | [OpenWrt port](docs/OPENWRT-PORT.md) | High; experimental port |
| Recover a dead/bricked unit | [Recovery](docs/RECOVERY.md) | — |

The recommended order is: root first (Samba), dump the flash, then decide
whether you need the vendor unlock or OpenWrt.

---

## What the lock actually is

The vendor web updater accepts an `HDR2` image only if:

1. the magic is `HDR2`, the declared length is sane, and the payload JAMCRC at
   `0x0c` matches `~crc32(payload[0x100:length])`;
2. on the Excitel build, the 8-byte model at `0x88` is `T2122EUZ` or
   `T2122ELZ` (other builds may accept a different string);
3. the 32-bit upgrade gate at `0x80` is `1`;
4. the version at `0x10` is acceptable to the installed `UpgradeSWVersion`
   comparison.

The CRC covers only the payload, so version/model/gate are a pure header edit.
The retail V1.30 image says `T2122` and gate `0`, which is why it is rejected
as-is. The Excitel V1.32EXU validator wants `T2122EUZ`.

There is **no `EULX` string** in these images. The Excitel version suffix is
`EXU` (`T2122-V1.33EXU`) and its model strings are `T2122EUZ` / `T2122ELZ`.
Public Airtel builds use the `AE` suffix (`T2122-V1.17AE`, `T2122-V1.26AE`);
their model string is not confirmed.

---

## Quick start: root without flashing

This uses the stock Samba share, which maps to `/` and runs as root, plus
Samba's classic `magic script` feature.

1. In the stock web UI, open **APP → Samba** and enable it. The share is
   `Samba_Share`, path `/`, user `admin`, password `1234` by default.
2. On Linux, with `smbclient` installed:

   ```sh
   cd unlocked-GX-Titatnium-2122A   # or whatever you named the clone
   ./tools/samba_telnet.sh 192.168.1.1 admin 1234
   telnet 192.168.1.1 23
   ```

3. You should get `uid=0(root)` with no password. Then make it persistent:

   ```sh
   /userfs/bin/tcapi set Account_TelnetEntry Active Yes
   /userfs/bin/tcapi set Account_TelnetEntry telnet_active Yes
   /userfs/bin/tcapi set System_Entry telnet_enable 1
   /userfs/bin/tcapi commit Account_TelnetEntry
   /userfs/bin/tcapi commit System_Entry
   /userfs/bin/tcapi save
   ```

   After a reboot, the vendor telnet is on **56090** (login `excitel`, password
   = the MAC on the label). Port 23 itself is not persistent.

Full manual steps, troubleshooting and cleanup:
[SAMBA-TELNET.md](docs/SAMBA-TELNET.md).

---

## Quick start: unlocked vendor firmware

The included images are the generic V1.30 vendor build with a patched header.
The vendor updater writes the **inactive** bank, so the stock firmware stays on
the other bank.

```sh
cd unlocked-GX-Titatnium-2122A   # or whatever you named the clone

# inspect the image (optional)
python3 tools/t2122a_patch.py --check \
    firmware/tclinux-T2122-V1.33EXU-unlocked.bin

# upload through the stock web UI:
#   http://192.168.1.1/cgi-bin/upgrade.asp
#   (or Manage -> Upgrade; the filename must contain "tclinux")
```

Or patch your own stock dump instead of using the included image:

```sh
python3 tools/t2122a_patch.py --preset excitel \
    -o /tmp/my-unlocked.bin /path/to/my-stock.bin
```

Included firmware:

| File | Model | Status | SHA256 |
|---|---|---|---|
| `firmware/tclinux-T2122-V1.33EXU-unlocked.bin` | `T2122EUZ` | Tested on Excitel | `72e946c4…45d07` |
| `firmware/tclinux-T2122-V1.33EXU-ELZ-untested.bin` | `T2122ELZ` | Untested guess, same payload | `e8732ade…1abad` |

The full hashes are in [FIRMWARE.md](docs/FIRMWARE.md). On the Excitel build
the header says `V1.33EXU` so the updater accepts it; the code is V1.30.

The updater preserves the config partition, so the existing WAN/PPPoE profile
normally survives. Check it before reconnecting the fibre.

---
<img width="735" height="1280" alt="photo_2026-11-20_17-21-05" src="https://github.com/user-attachments/assets/53f506df-85cb-47ce-bd93-9dd4f5fa04ff" />

## What is in the kit

```
README.md                       this file
docs/
  ACCESS-RECOVERY.md            all logins, UART/bldr, boot flag, locked-out fixes
  SAMBA-TELNET.md               root shell via Samba magic script (no flash)
  FIRMWARE.md                   HDR2 format, checks, patcher, tested images
  VARIANTS.md                   Excitel / Airtel / other; how to find your model
  RECOVERY.md                   banks, boot flag, UART/bldr, mtd, dumps
  OPENWRT-PORT.md               optional OpenWrt port (build + flash + dumb AP)
firmware/
  tclinux-T2122-V1.33EXU-unlocked.bin    tested vendor image, EUZ
  tclinux-T2122-V1.33EXU-ELZ-untested.bin  same payload, ELZ, untested guess
  openwrt-econet-en7528-titanium_2122a_slave-squashfs-tclinux.trx
  openwrt-titanium-slave-le.trx          same OpenWrt image, deployed name
  openwrt-...manifest
  flagsec.bin                            128 KiB boot-flag sector (0x31)
tools/
  t2122a_patch.py               universal HDR2 unlock/inspect tool
  samba_telnet.sh               one-command Samba magic-script root
  smb.conf                      SMB1/NTLMv1 client config for the old Samba
  mtdwrite, mtdwrite.c          raw MTD erase/write/verify for OpenWrt
  flash_slave_le.py             stock-telnet OpenWrt slave installer
  bldr_set_main_wait.py         bldr: return the boot flag to main (0x30)
  bldr_flashargs.py             bldr raw command runner
  serial_cmd.py                 UART command runner (OpenWrt prompt)
  ubi_provision.py              UBIFS overlay provisioning helper
  rootfs_data.ubifs             empty UBIFS volume image
config/                         working OpenWrt .config and build metadata
source/                         OpenWrt source changes (DTS, image recipe, ...)
```

---

## After you have root

- Dump both firmware banks and the config partition before changing anything.
  The commands are in [RECOVERY.md](docs/RECOVERY.md).
- Change the default web/Samba/telnet passwords, or turn the services off.
- If you enable vendor telnet, remember it listens on 56090 with a login based
  on the device MAC.
- Do not leave `magic script = telnet_start.sh` in `smb.conf`: it is a
  permanent remote-root hole while Samba is enabled.

---

## FAQ

**The web upgrade says "Wrong file formate" / "Upgrade failed".**
The model string or the CRC/length is wrong. Run
`python3 tools/t2122a_patch.py --check image.bin` and compare with the header
table in [FIRMWARE.md](docs/FIRMWARE.md). A common mistake is using the wrong
model preset for your variant.

**Can I flash the OpenWrt `.trx` through the web UI?**
No. It is a different container and has no `HDR2` header. The vendor UI will
reject it. Use `mtdwrite` from a running OpenWrt, or the installer script from
stock. Renaming it does not help.

**Will this work on Airtel?**
The hardware and the header trick are the same, but no Airtel unit was available
to confirm the header values. Public reports show Airtel firmware versions
`T2122-V1.17AE` and `T2122-V1.26AE`, so the suffix is `AE`, not `EXU`. The model
string is not confirmed; `T2122ELZ` is only a guess. Patch your own Airtel dump
and read its header first; see [VARIANTS.md](docs/VARIANTS.md).

**I only have the router, no dump. Can I still unlock?**
Yes: enable Samba, get root, dump the flash, then patch your own image. If you
do not want to dump, the included Excitel-based image is the tested fallback;
it is generic V1.30 and preserves your config partition.

**Is the stock firmware destroyed?**
The vendor updater writes the inactive bank and flips the boot flag, so the
stock image remains on the other bank. Do not erase both banks. The OpenWrt
port also lives on the slave bank.

---

## Safety and legal

- Use this only on hardware you own.
- The vendor firmware is proprietary. This kit patches headers and documents
  the process; it does not grant you a license to redistribute the vendor code.
  If you redistribute an image, you are responsible for the consequences.
- Keep a full dump and know how to reach the bootloader before you flash.
- Never publish your `romfile`, full-flash dump, MAC, serial, Wi-Fi keys or
  PPPoE credentials.
- The authors are not responsible for bricked units, voided warranties, or ISP
  terms-of-service violations.
