# Titanium T2122A — OpenWrt port (optional advanced path)

This is the development log and build recipe for the working OpenWrt
installation on the **Titanium T2122A** GPON ONT (EcoNet/EN7528, 1×PON,
2×GbE, 1×FXS voice). It is not needed for the vendor unlock; use
[../README.md](../README.md) for that.

The board is **not** a JCOW407. The port lives on the slave bank and leaves the
stock vendor firmware untouched on the main bank. That dual-bank layout is the
recovery path.

IP addresses, interface names, SSIDs and keys below are examples from the
development unit. Replace them with your own. Paths are relative to the kit
root unless stated otherwise. Never publish a dump or a live configuration: it
contains your MAC, serial, Wi-Fi keys and ISP credentials.

Date of this snapshot: 2026-11-17.

---

## 0. Current state (verified after a full reboot)

| Item | Value |
|---|---|
| Booted system | OpenWrt 6.18.36, from `tclinux_slave` (mtd4) |
| Boot flag at absolute flash `0xdfc0000` | `0x31` = slave/OpenWrt (`0x30` = main/stock) |
| Management IP | `192.168.1.99/24` on `br-lan` |
| Default gateway / DNS | `192.168.1.1` (the main OpenWrt gateway) |
| Mode | **Dumb AP / bridge** — DHCP, DNS, IPv6 RA and firewall all disabled |
| LAN | `lan1` = switch port 1 = PHY 9; `lan2` = switch port 2 = PHY 10; ports 3/4 have no jacks and are disabled |
| LAN link used for management | `lan2`, measured **1000 Mbit/s full duplex**; `lan1` was also verified at 1 Gbit/s earlier |
| Wi-Fi 2.4 GHz | SSID `Titanium-2122A`, ch 1, HT20, WPA2-PSK/AES |
| Wi-Fi 5 GHz | SSID `Titanium-2122A-5G`, ch 36 (radio reported ch 40), VHT80, WPA2-PSK/AES |
| Status LEDs | `green:power` solid on; `blue:wan` solid on while Wi-Fi interface `phy0-ap0` has link (blinks on traffic); `red:status` heartbeat. No `ledctl` binary — see §6. |
| LuCI | `http://192.168.1.99/` and `https://192.168.1.99/` (also worked on the old `.1` address); user `root`, **empty password** |
| SSH | `ssh root@192.168.1.99` (dropbear, empty password accepted) |
| Persistent overlay | `/dev/ubi0_0 on /overlay type ubifs`, `rootfs_data` volume on `opt0` (mtd7) |
| Stock fallback | Stock V1.32EXU still intact on the main bank (`tclinux`, mtd2) |
| Host-side HTTP server | any HTTP server on the LAN (examples below use `192.168.1.10`) |
| Host NIC to the AP | the host NIC plugged into **LAN2** (examples use `eth0`) |

Verified listeners on the AP after dumb-AP conversion: only TCP 22 (SSH) and
80/443 (uhttpd). Nothing listens on 53 or 67 — DHCP/DNS come from the gateway at
`192.168.1.1` through the bridge.

---

## 1. Hardware and flash layout

From the board DTS and live `/proc/mtd`:

```
mtd0  0x00040000  bootloader
mtd1  0x00040000  romfile
mtd2  0x01900000  tclinux          (main bank, stock firmware — DO NOT OVERWRITE)
mtd3  0x01500000  rootfs_main
mtd4  0x01900000  tclinux_slave    (OpenWrt image lives here)
mtd5  0x01500000  rootfs           (overlaps part of mtd4 — see gotcha #3)
mtd6  0x01020000  rootfs_data
mtd7  0x00800000  opt0             (UBIFS overlay: rootfs_data volume)
mtd8  0x00800000  opt1
mtd9  0x01000000  ubifs
mtd10 0x00240000  reservearea      (base 0xddc0000; boot flag at +0x200000)
```

Absolute flash offsets used by the image/DTS:

```
tclinux         @ 0x0080000
tclinux_slave   @ 0x1980000
opt0            @ 0x3280000
opt1            @ 0x3a80000
ubifs           @ 0x4280000
reservearea     @ 0xddc0000   (0x240000 long)
boot flag       @ 0xdfc0000   (reservearea + 0x200000)
```

Other verified hardware facts:

- SoC: EcoNet EN7528, MIPS 1004Kc, little-endian, `econet/en7528` subtarget.
- RAM: 256 MB DDR3, ~240 MB usable (`0x2000`–`0x0effffff`).
- SPI-NAND: FORESEE FS35ND02GS3Y2, 256 MB, ID `cd eb 11`.
- Wi-Fi: MediaTek MT7603 (2.4 GHz) and MT7663 (5 GHz) on PCI; `14c3:7603` and `14c3:7663`.
- Ethernet: MT7530 switch with integrated GPHYs on MDIO 9 (LAN1) and 10 (LAN2).
- LEDs: single tri-colour LED on GPIO 2/3/4 (red/green/blue, **active low**).
  RJ45 link/activity LEDs are driven by the switch/PHY in hardware.
- Reset button: GPIO 0, active low. **There is no WPS button**; GPIO 1 reads low
  on the stock board and must not be claimed as a key.
- FXS/voice line present; no OpenWrt telephony driver was configured.

---

## 2. Boot-bank switching

The bootloader selects a bank from a single byte at absolute flash `0xdfc0000`:

- `0x30` → boot **main** (`tclinux`, stock)
- `0x31` → boot **slave** (`tclinux_slave`, OpenWrt)

Read it from the host side (the target has no `od`):

```sh
ssh root@192.168.1.99 'dd if=/dev/mtd10 bs=1 skip=2097152 count=1 2>/dev/null' | od -An -tx1
# expected: 31
```

Direction-dependent write rules (important):

- `0x31 → 0x30`: only bit 0 is cleared. The bootloader's non-erasing
  `flash dfc0000 ...` command works. Use `tools/bldr_set_main_wait.py`, which
  was proven on this unit. It enters bldr, does `memwl 80001000 30ffffff`, then
  `flash dfc0000 80001000 4 0`, and requires a reset to take effect.
- `0x30 → 0x31`: a bit must be set from 0 to 1, so the sector needs an erase
  first. From stock firmware use `/userfs/bin/mtd erasesector 2097152
  reservearea` followed by `/userfs/bin/mtd writeflash /tmp/flagsec.bin 131072
  2097152 reservearea`. `firmware/flagsec.bin` in this folder is a complete
  128 KiB sector image with `0x31` in byte 0 and `0xff` elsewhere.

Stock telnet (only when the **main/stock** bank is booted): `192.168.1.1:56090`,
the stock login for your ISP (Excitel units commonly ship `excitel` / `exc@123`; check the label).

Bootloader serial console: **115200 8N1**, 3-second "Press any key" window;
send `b`; login `telecomadmin` / `nE7jA%5m`; prompt `bldr>`.

---

## 3. The shipped firmware image

```
firmware/openwrt-titanium-slave-le.trx
firmware/openwrt-econet-en7528-titanium_2122a_slave-squashfs-tclinux.trx
```

Both files are byte-identical copies of the tested build:

- Size: **9,243,088 bytes** (~8.9 MiB), well under the 25 MiB (0x1900000) mtd4.
- SHA256: `40464cce077f5cfbaf8683cbacf3ae0f3c8c7d89ca1d40b1dc0e7e219e765c30`
- Format: little-endian TRX (`TRX_MODEL := Dewberry`).
- Kernel command line: `ubi.mtd=opt0`.
- Key packages (see `firmware/*.manifest` for the full list): `luci-ssl`,
  `luci-light`, `luci-mod-admin-full`, `luci-theme-bootstrap`, `luci-app-firewall`,
  `luci-app-package-manager`, `uhttpd`, `uhttpd-mod-ubus`, `px5g-mbedtls`,
  `kmod-mt7603`, `kmod-mt7615e`, `kmod-mt7663-firmware-ap`, `kmod-mt76-core`,
  `kmod-mt76-connac`, `wpad-basic-mbedtls`, `hostapd-common`,
  `luci-app-econet-xpon`.

**Why the image has a jump stub:** this bldr is a "free bootbase" build. It
decompresses the kernel at `0x80002000`, while OpenWrt links it at
`0x80020000`. The image recipe prepends a little-endian `j 0x80020000` stub
(bytes `00 80 00 08`) plus a `0x1E000` pad:

```
IMAGE/tclinux.trx := append-kernel | tclinux-free-bootbase-jump | lzma | tclinux-trx
```

Flashing a kernel without this stub produces a dead/silent boot.

---

## 4. Source changes needed to rebuild

`source/` contains only the files that differ from a clean OpenWrt tree, in
their original relative paths. Copy them over the tree at
`/path/to/openwrt-econet-gpon` before building.

| File | Purpose |
|---|---|
| `source/target/linux/econet/dts/en7528_titanium_2122a_slave.dts` | Board DTS for slave-bank boot. `bootargs = "ubi.mtd=opt0"`, 2-port LAN map, PHY-ID compatibles, correct reset LED/keys, no WPS key. |
| `source/target/linux/econet/dts/en7528_titanium_2122a.dts` | Same board, main-bank variant (rootfs at `0x480000`). |
| `source/target/linux/econet/patches-6.18/782-net-dsa-mt7530-let-en7528-gphys-settle-after-reset.patch` | Adds a 200 ms delay after EN7528 GPHY reset in `mt7530.c`, before the first MDIO scan. |
| `source/target/linux/econet/base-files/etc/board.d/02_network` | Maps `titanium,t2122a` to `lan1 lan2` (not `lan1..lan4`). |
| `source/target/linux/econet/image/en7528.mk` | `Device/titanium_2122a` + `_slave`, `DEVICE_PACKAGES`, free-bootbase jump stub, TRX recipe. |
| `config/build.config` | The exact working `.config`; copy to the tree root as `.config`. |
| `config/config.buildinfo`, `config/profiles.json` | Build metadata and generated device profiles. |

Build:

```sh
cd /path/to/openwrt-econet-gpon
cp config/build.config .config
# after copying source/ files into target/linux/econet:
make defconfig
make -j$(nproc)
```

The image lands in `bin/targets/econet/en7528/` as
`openwrt-econet-en7528-titanium_2122a_slave-squashfs-tclinux.trx`.

**Config gotcha:** `make defconfig` does *not* turn explicit
`# CONFIG_PACKAGE_foo is not set` lines into `y`, even when the device's
`DEVICE_PACKAGES` lists them. On a stale config, force them first:

```sh
sed -i -E 's/^# CONFIG_PACKAGE_(luci-ssl|luci-light|luci-mod-admin-full|luci-theme-bootstrap|luci-app-firewall|luci-proto-ppp|uhttpd|px5g-mbedtls|kmod-mt7603|kmod-mt7615e|kmod-mt7663-firmware-ap) is not set$/CONFIG_PACKAGE_\1=y/' .config
echo 'CONFIG_PACKAGE_uhttpd-mod-ubus=y' >> .config
make defconfig
```

The shipped `config/build.config` already has these set, so this is only needed
if you regenerate from an older config.

---

## 5. Flashing guide

### 5.1 Re-flash OpenWrt from a running OpenWrt (recommended, no power cycle)

This is how the final image was installed. It works at either `192.168.1.1`
(before dumb-AP conversion) or `192.168.1.99` (now).

On the host:

```sh
# serve this kit folder; the paths below are relative to it
python3 -m http.server 8000 --bind 192.168.1.10
# If the host has two NICs on 192.168.1.0/24, force the right one:
sudo ip route add 192.168.1.99 dev eth0 src 192.168.1.10
```

On the AP:

```sh
cd /tmp
wget -q -O mtdwrite  http://192.168.1.10:8000/mtdwrite
wget -q -O new.trx   http://192.168.1.10:8000/openwrt-titanium-slave-le.trx
chmod +x mtdwrite
sha256sum new.trx
# must print 40464cce077f5cfbaf8683cbacf3ae0f3c8c7d89ca1d40b1dc0e7e219e765c30
setsid sh -c '/tmp/mtdwrite /dev/mtd4 /tmp/new.trx > /tmp/flash.log 2>&1; \
  echo EXIT=$? >> /tmp/flash.log; reboot' </dev/null >/dev/null 2>&1 &
```

`mtdwrite` usage is `mtdwrite <mtddev> <file>`; it erases, writes and verifies
(`VERIFY OK`). Using `setsid` keeps the flash alive if the SSH session drops
when the overlapping squashfs is overwritten. Wait for the reboot, then
 reconnect (with the routing fix above if needed).

### 5.2 First install from stock main firmware (telnet)

Only run this while **stock** is booted from the main bank:

```sh
python3 tools/flash_slave_le.py
# pass --host/--user/--password/--url if your unit differs from the defaults
```

The script logs into `192.168.1.1:56090` (`excitel` / `exc@123`), downloads the
TRX from the host HTTP server, writes it to `tclinux_slave`, erases and writes
the boot-flag sector with `flagsec.bin`, verifies both, and prints
`HDRCMP=0` and `FLAGCMP=0`. Only after those checks should you power-cycle.

### 5.3 Serial/bldr recovery

- Console: `/dev/ttyUSB0`, 115200 8N1. Needs root (`sudo`).
- `tools/serial_cmd.py '<shell command>'` runs commands against the OpenWrt
  prompt `root@OpenWrt:~# ` (it does not see a `login:` prompt — the serial
  console auto-logs in). Do not put `__DONE__` markers in commands sent through
  that helper, because the echoed command contains the marker and ends the read.
- `tools/bldr_flashargs.py '<bldr command>' ...` attaches to bldr, logs in and
  runs raw bldr commands.
- To return to stock: `python3 tools/bldr_set_main_wait.py`, then reset/power-cycle.
- To boot OpenWrt again from stock: use 5.2, or erase+write `0x31` into the flag
  sector as described in §2.

### 5.4 One-time overlay provisioning (only on a fresh/empty opt0)

This kernel has **JFFS2 disabled**, so the writable overlay must be UBIFS on the
`opt0` partition. It is already provisioned on this unit. If you ever erase
mtd7, re-create it from a running OpenWrt shell:

```sh
wget -O /tmp/rootfs_data.ubifs http://192.168.1.10:8000/rootfs_data.ubifs
ubiformat /dev/mtd7 -y -q
ubiattach -m 7
ubimkvol /dev/ubi0 -N rootfs_data -m
ubiupdatevol /dev/ubi0_0 /tmp/rootfs_data.ubifs
mount -t ubifs /dev/ubi0_0 /mnt
```

`tools/rootfs_data.ubifs` is the empty image used here (geometry: min I/O 2048,
LEB 126976, 36 LEBs ≈ 4.3 MiB). `tools/ubi_provision.py` is the script that
performed these steps; it was written against an older `# ` prompt and uses an
`__DONE__` marker, so prefer the commands above on the current build.

---

## 6. Dumb-AP configuration (applied and verified)

The AP is a pure layer-2 bridge: it forwards DHCP/DNS from the main gateway and
does no routing, NAT, DHCP, DNS or firewalling of its own. All changes are in
the persistent UBIFS overlay.

```sh
uci set system.@system[0].hostname='t2122a'

uci delete network.lan.ipaddr
uci add_list network.lan.ipaddr='192.168.1.99/24'
uci set network.lan.gateway='192.168.1.1'
uci add_list network.lan.dns='192.168.1.1'

uci set dhcp.lan.ignore='1'

uci commit network
uci commit dhcp
uci commit system

/etc/init.d/dnsmasq stop;  /etc/init.d/dnsmasq disable
/etc/init.d/odhcpd stop;   /etc/init.d/odhcpd disable
/etc/init.d/firewall stop; /etc/init.d/firewall disable
/etc/init.d/network restart
```

Wi-Fi (the generated config starts with both radios *disabled* — this is why an
otherwise working image showed no `iw dev` interfaces):

```sh
uci set wireless.default_radio0.ssid='Titanium-2122A'
uci set wireless.default_radio0.encryption='psk2+ccmp'
uci set wireless.default_radio0.key='change-me-please'
uci set wireless.default_radio0.disabled='0'

uci set wireless.default_radio1.ssid='Titanium-2122A-5G'
uci set wireless.default_radio1.encryption='psk2+ccmp'
uci set wireless.default_radio1.key='change-me-please'
uci set wireless.default_radio1.disabled='0'

uci commit wireless
wifi reload
```

LEDs — the stock `ledctl`/`tcledctrl` utility does not exist in OpenWrt. The
GPIO mapping itself is in the DTS (`gpio-leds`: red GPIO 2, green GPIO 3, blue
GPIO 4, all active-low); triggers are configured persistently in UCI:

```sh
uci add system led
uci set system.@led[-1].name='WiFi'
uci set system.@led[-1].sysfs='blue:wan'
uci set system.@led[-1].trigger='netdev'
uci set system.@led[-1].dev='phy0-ap0'
uci set system.@led[-1].mode='link tx rx'
uci set system.@led[-1].default='0'

uci add system led
uci set system.@led[-1].name='Status'
uci set system.@led[-1].sysfs='red:status'
uci set system.@led[-1].trigger='heartbeat'
uci set system.@led[-1].default='0'

uci commit system
/etc/init.d/led restart
```

`green:power` is left alone; its DTS alias makes it solid on. Note that the
`phy0radio` mac80211 trigger stayed dark on this build, so the blue LED uses
`netdev` on the 2.4 GHz AP interface instead (solid with carrier, blinking on
TX/RX). Verify with:

```sh
for d in /sys/class/leds/*; do
  echo "$(basename $d): trigger=$(sed -n 's/^.*\[\(.*\)\].*$/\1/p' $d/trigger) brightness=$(cat $d/brightness)"
done
```

Expected running state:

```
ip -4 addr show br-lan | grep inet
    inet 192.168.1.99/24 brd 192.168.1.255 scope global br-lan
ip route
    default via 192.168.1.1 dev br-lan
    192.168.1.0/24 dev br-lan scope link  src 192.168.1.99
netstat -ltn          # only 22, 80, 443
iw dev                # phy0-ap0 (ch 1), phy1-ap0 (ch 36/40)
brctl show            # br-lan: lan1 lan2 phy0-ap0 phy1-ap0
```

---

## 7. Standard gotchas / troubleshooting

1. **WPS key / GPIO 1.** Do not add a WPS button. GPIO 1 reads low on this
   board; claiming it as a key produces spurious events. Only the reset key
   (GPIO 0, active low) exists.

2. **PHY 9 race.** The first MDIO scan after reset could read `phy_id=0`, so
   LAN1 stayed dead. Fix = DT compatible `ethernet-phy-id03a2.9491` for the
   GPHYs **plus** the 200 ms `msleep()` in the mt7530 patch. Both are required.
   Verify with:
   `dmesg | grep -E 'mt7530-0:09|mt7530-0:0a'` → both `id=0x03a29491`.

3. **mtd4 overlaps mtd5.** Writing mtd4 (`tclinux_slave`) from the running
   OpenWrt system overwrites parts of the mounted squashfs (`rootfs`, mtd5).
   Transient `SQUASHFS error` messages and a degraded shell during the write
   are expected; finish with `reboot` and they disappear.

4. **JFFS2 is disabled in this kernel.** Do not expect a JFFS2 `rootfs_data`.
   Overlay is UBIFS on `opt0`; `bootargs = "ubi.mtd=opt0"` is mandatory, and
   mtd7 must be formatted/provisioned as in §5.4.

5. **Boot-flag direction.** `0x30 → 0x31` needs erase + writeflash;
   `0x31 → 0x30` is a bit-clear and bldr's non-erasing `flash` works. Getting
   this backwards leaves the board trying to boot the wrong bank.

6. **Free-bootbase jump stub.** Missing the `00 80 00 08` + `0x1E000` pad =
   silent boot. This is the single most important image-recipe detail.

7. **Two-port board.** `02_network` must map only `lan1 lan2`. Enabling ports 3/4
   or using the JCOW407 four-port map gives dead interfaces.

8. **Serial console behaviour.** It auto-logs in; there is no `login:` prompt
   in OpenWrt. Prompt is `root@OpenWrt:~# `. The serial device needs root.
   In bldr use the 3-second window and single `b`.

9. **Host has two NICs on the same subnet.** If the management NIC and the main
   gateway NIC are both on `192.168.1.0/24`, Linux may route `192.168.1.99` out
   the wrong one, producing "No route to host" even though the AP is up. Bind
   the source per command:
   `ssh -b 192.168.1.10 root@192.168.1.99` or
   `sudo ip route add 192.168.1.99 dev eth0 src 192.168.1.10`.

10. **LuCI 403 on first fetch.** The bare `/` page is a small redirect page and
    `/cgi-bin/luci/` returns 403 until authenticated — that is the login page,
    not a broken install. Log in with user `root` and the (currently empty)
    password. An authenticated request to
    `/cgi-bin/luci/admin/status/overview` returns HTTP 200 with title
    `OpenWrt | Overview`.

11. **5 GHz firmware warning.** During boot `mt7615e` logs
    `mediatek/mt7663pr2h.bin not found, switching to ...rebb.bin`. This is
    normal for this firmware package; the radio still initialises.

12. **Missing target utilities.** BusyBox on the AP has no `hostname`, `od`, or
    useful `ethtool`. Use `uci get system.@system[0].hostname`, pipe `dd` output
    to the host's `od`, and read `/sys/class/net/lanX/speed` and
    `/sys/class/net/lanX/duplex` (`1000`, `full`).

13. **Root password left empty** deliberately so scripted SSH keeps working.
    If you set one in LuCI, remember to update any automation. LuCI itself
    accepted the blank password (verified).

14. **No `ledctl` in OpenWrt.** The stock firmware used `tcledctrl` with
    `/userfs/led.conf`; OpenWrt uses `gpio-leds` in the DTS plus UCI
    `system.led` sections. Seeing only the green power LED lit is normal until
    triggers are assigned (§6). The RJ45 jack LEDs are driven by the MT7530
    PHYs in hardware and are not GPIO LEDs.

15. **Do not power-cycle unnecessarily.** Software `reboot` is safe and was
    used throughout. Physical power cycling is only needed when switching
    banks in bldr or when asked.

---

## 8. Verification checklist

Run these after any reflash or bank switch:

```sh
ssh root@192.168.1.99
cat /proc/cmdline                       # ubi.mtd=opt0
cat /proc/uptime                        # small value => normal boot, not failsafe
ip -4 addr show br-lan | grep inet     # 192.168.1.99/24
ip route | head -2                     # default via 192.168.1.1
cat /sys/class/net/lan2/speed          # 1000
cat /sys/class/net/lan2/duplex         # full
iw dev | grep -E 'ssid|channel'        # both APs
netstat -ltn                           # 22, 80, 443 only
mount | grep overlay                   # ubifs upperdir
dmesg | grep -iE 'mt7603|mt7615|mt7663' | head
for d in /sys/class/leds/*; do echo "$(basename $d): $(sed -n 's/^.*\[\(.*\)\].*$/\1/p' $d/trigger) $(cat $d/brightness)"; done
# green:power none 1, blue:wan netdev 1, red:status heartbeat 0/1
```

From the host (with the routing fix from gotcha #9):

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.1.99/
curl -k -s -o /dev/null -w '%{http_code}\n' https://192.168.1.99/
ssh root@192.168.1.99 'dd if=/dev/mtd10 bs=1 skip=2097152 count=1 2>/dev/null' | od -An -tx1
# 31 = OpenWrt / slave bank
```

To return to stock: run `python3 tools/bldr_set_main_wait.py`, reset, verify
the flag byte reads `30`, and confirm the stock firmware boots from the main
bank. Keep a full dump of your own stock flash before you start; it is the only
reliable way back if the vendor bank is ever damaged.

---

## 9. Folder contents

```
docs/OPENWRT-PORT.md                        this report
firmware/openwrt-titanium-slave-le.trx        tested image (deployed name)
firmware/openwrt-econet-en7528-titanium_2122a_slave-squashfs-tclinux.trx
                                            same image, original build name
firmware/openwrt-econet-en7528-titanium_2122a_slave.manifest
firmware/flagsec.bin                        128 KiB boot-flag sector containing 0x31
config/build.config                         working .config
config/config.buildinfo, config/profiles.json
source/...                                  only the modified OpenWrt source files
tools/mtdwrite, tools/mtdwrite.c            raw MTD erase/write/verify utility
tools/serial_cmd.py                         prompt-based serial command runner
tools/flash_slave_le.py                     stock-telnet installer + boot-flag writer
tools/bldr_set_main_wait.py                 bldr helper: return to stock bank
tools/bldr_flashargs.py                     bldr raw command runner
tools/ubi_provision.py                      original UBIFS provisioning script
tools/rootfs_data.ubifs                     empty UBIFS volume image
```

Build and boot logs from the development unit are intentionally not shipped:
they contain host paths and unit-specific addresses.
