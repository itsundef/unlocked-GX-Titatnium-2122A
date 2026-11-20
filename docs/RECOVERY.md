# Recovery and flash layout

The T2122A has two independent firmware banks. The vendor updater writes the
inactive bank, and the OpenWrt port lives on the slave bank, so the stock bank
remains the recovery path. A bad image written to the bank you are currently
running from can still leave the board without a network; the way back is the
boot flag plus the bootloader console.

## 1. Vendor `/proc/mtd`

This is the map from the stock V1.32EXU firmware. **The OpenWrt DTS numbers are
different**; use the names, or the absolute offsets below, not the OpenWrt mtd
indices.

```
mtd0  0x00040000  bootloader
mtd1  0x00040000  romfile
mtd2  0x003d863a  kernel
mtd3  0x00e10000  rootfs
mtd4  0x01900000  tclinux          <- main bank
mtd5  0x003d822c  kernel_slave
mtd6  0x00d90000  rootfs_slave
mtd7  0x01900000  tclinux_slave    <- second bank
mtd8  0x00800000  opt0
mtd9  0x00800000  opt1
mtd10 0x01000000  ubifs
mtd11 0x00240000  reservearea
```

Absolute offsets:

```
tclinux         0x0080000
tclinux_slave   0x1980000
opt0            0x3280000
opt1            0x3a80000
ubifs           0x4280000
reservearea     0xddc0000
boot flag       0xdfc0000   (reservearea + 0x200000)
```

The boot flag is one byte:

- `0x30` -> boot **main** / stock (`tclinux`, mtd4)
- `0x31` -> boot **slave** (`tclinux_slave`, mtd7)

Read it from a running OpenWrt system (the OpenWrt DTS puts `reservearea` at
`mtd9`; check `/proc/mtd` if your layout differs):

```sh
dd if=/dev/mtd9 bs=1 skip=2097152 count=1 2>/dev/null | od -An -tx1
# 31 = slave, 30 = main
```

## 2. Switching banks

Direction matters because the flag is a bit, and the bootloader's `flash`
command does not erase:

- `0x31 -> 0x30`: only bit 0 is cleared. Use the bootloader:
  ```
  memwl 80001000 30ffffff
  flash dfc0000 80001000 4 0
  ```
  `tools/bldr_set_main_wait.py` does this over the serial console and then
  resets. It was tested on the development unit.

- `0x30 -> 0x31`: a bit must go from 0 to 1, so the sector must be erased
  first. From stock firmware:
  ```sh
  /userfs/bin/mtd erasesector 2097152 reservearea
  /userfs/bin/mtd writeflash /tmp/flagsec.bin 131072 2097152 reservearea
  ```
  `firmware/flagsec.bin` is a 128 KiB sector image with `0x31` in byte 0 and
  `0xff` elsewhere. Verify it with `cmp` after writing.

Getting the direction backwards leaves the board trying to boot the wrong bank.
If both banks are invalid, only the bootloader console can recover it.

## 3. Serial console and `bldr`

- UART: **115200 8N1**, 3.3 V logic. The header is on the board; use a 3.3 V
  USB UART, not RS-232 levels.
- Power on and press a key within the 3-second window, then `b`.
- Bootloader login (default): `telecomadmin` / `nE7jA%5m`.
- Prompt: `bldr>`.
- `help` lists the commands; `imginfo` shows the current image and boot flag.

Helpers in this kit (they need `pyserial` and `/dev/ttyUSB0`):

```sh
python3 tools/bldr_flashargs.py 'imginfo' 'help'
python3 tools/bldr_set_main_wait.py     # 0x31 -> 0x30, then reset
```

`bldr_flashargs.py` sends raw commands. `bldr_set_main_wait.py` waits for the
boot prompt, logs in, writes `0x30`, and prints the result. Both write their log
to `/tmp`.

## 4. Restoring the stock bank

If the stock bank is still intact and only the boot flag points at a bad slave
image, the fix is `0x31 -> 0x30` above. No reflash is needed.

If the stock bank itself was overwritten (only do this if you have a full dump):

```sh
# on the device, from a root shell, with the dump at /tmp/mtd4.bin
/userfs/bin/mtd -f write /tmp/mtd4.bin 26214400 0 tclinux
```

Do not write a 25 MiB partition image with a size that does not match. The
vendor `mtd` command takes `write <file> <length> <offset> <partition>`.

For OpenWrt, `tools/mtdwrite` takes `<mtddev> <file>` and erases, writes and
verifies. Use it only from a running OpenWrt system, and target the partition
that is **not** currently mounted:

```sh
/tmp/mtdwrite /dev/mtd4 /tmp/openwrt.trx
```

## 5. Dumping your own firmware first

Before any unlock, get a copy of both banks and the config partition. From the
Samba root shell (or the vendor telnet):

```sh
cat /dev/mtd4  > /tmp/tclinux-main.bin
cat /dev/mtd7  > /tmp/tclinux-slave.bin
cat /dev/mtd1  > /tmp/romfile.bin
cat /dev/mtd11 > /tmp/reservearea.bin
```

`/tmp` is RAM; copy the files off over SMB (`Samba_Share` maps to `/`) or serve
them with `wget` from the device. Keep the resulting files private: the romfile
contains your MAC, serial and ISP credentials, and the firmware may contain
device-specific keys.

Verify a vendor image before flashing:

```sh
python3 tools/t2122a_patch.py --check tclinux-main.bin
```

## 6. If the web upgrade fails

- `Wrong file formate`, or `Upgrade failed, please retry!`: the model string or
  the CRC/length is wrong. Run `--check` and compare the header table in
  [FIRMWARE.md](FIRMWARE.md).
- The web UI accepts only an `HDR2` vendor image whose filename contains
  `tclinux`. Renaming `openwrt...trx` to `tclinux...bin` does **not** make it a
  vendor image; it is still a TRX and must be flashed with `mtd`.
- If the upload succeeds but the device does not come back, do not panic and do
  not erase the other bank. Connect UART, inspect `imginfo`, and switch the flag
  back to `0x30`.
- If Samba is still up on the dead bank (rare), the magic-script route can give
  a shell without UART.

## 7. Power-cycle policy

Prefer a software reboot. Power-cycle only when:

- the bootloader asks for it after a bank switch,
- the device is unresponsive and UART shows no progress,
- you are physically switching the boot flag.

Every unnecessary power cycle is a chance to disturb the fibre or the NAND.
