# Access, credentials, and "I'm locked out" recovery

Everything needed to get back in, in one place. All credentials below are
**vendor/ISP defaults**, not unit-specific secrets — they are safe to publish.
An ISP can change them via TR-069, and owners often change them themselves, so
treat them as starting points, not guarantees. Do not publish your own dump,
MAC, serial number, Wi-Fi key or PPPoE credentials.

> Only use this on hardware you own or are authorised to service.

## 1. Credentials quick reference

| Access method | Where | User | Password | Notes |
|---|---|---|---|---|
| Stock web UI (Excitel, before provisioning) | `http://192.168.1.1/` | `excitel` | `exc@123` | Excitel stock default; often changed by the ISP |
| Stock web UI (generic V1.30/V1.32) | `http://192.168.1.1/` | `admin` | `nE7jA%5m` | Also `GENEXIS`/`1234` and `user3`/`1234` |
| Stock web UI (after ISP provisioning) | `http://192.168.1.1/` | `admin` | MAC from the label | Lowercase, no separators; varies by build/ISP |
| Samba share | `\\192.168.1.1\Samba_Share` | `admin` | `1234` | Share maps to `/` and runs as root; enable under APP → Samba |
| One-shot root telnet | `192.168.1.1:23` | — | — | Started by the Samba magic script; no password, `uid=0(root)` |
| Persistent vendor telnet (generic V1.30/V1.32) | `192.168.1.1:56090` | `admin` | `1234` | `/usr/etc/passwd`, normal `/bin/login` |
| Persistent vendor telnet (Excitel after provisioning) | `192.168.1.1:56090` | `excitel` | MAC from the label | Enabled with `tcapi`, survives reboot |
| Bootloader (bldr) | UART, 115200 8N1 | `telecomadmin` | `nE7jA%5m` | 3-second key window, press a key then `b`; prompt `bldr>` |
| OpenWrt SSH | `192.168.1.99` (or `.1`) | `root` | empty | After the OpenWrt port; dropbear |
| OpenWrt LuCI | `http://192.168.1.99/` | `root` | empty | 403 on first fetch is the login page, not a broken install |
| OpenWrt serial console | UART, 115200 8N1 | auto-login `root` | — | No `login:` prompt; shell prompt is `root@OpenWrt:~#` |

The device MAC is printed on the label. For the MAC-as-password forms, use the
lowercase hex digits with no colons or dashes.

If a web password has been changed and you do not know it, skip straight to the
Samba route (§2) or the bootloader (§3).

### Defaults are not guaranteed — dump the real ones from your own unit

The bootloader login above (`telecomadmin` / `nE7jA%5m`) was confirmed working
on the development unit by serial capture, but ISPs routinely change the
web/telnet accounts through TR-069 after installation. On the live Excitel
unit, after provisioning, the observed logins were web `admin` / MAC and telnet
56090 `excitel` / MAC (before provisioning the web login was
`excitel` / `exc@123`). So trust your own dump, not any published table.

While you still have a root shell, read the account table and system passwd:

```sh
# vendor account table: web, telnet, FTP and console accounts
grep -A12 '<Account>' /userfs/romfile*.cfg

# system accounts used by /bin/login on the 56090 telnet service
cat /usr/etc/passwd
cat /usr/etc/shadow 2>/dev/null

# the port the telnet service really listens on
grep telnet /usr/etc/services
```

For reference, the stock V1.30/V1.32 rootfs extracted during this project
contains:

```xml
<Account>
  <TelnetEntry  Active="Yes" telnet_username="admin" telnet_passwd="1234" telnet_port="23" telnet_active="Yes" />
  <FtpCommon    Active="No"  ftp_username="admin"   ftp_passwd="1234"   ftp_port="21" />
  <ConsoleEntry Active="Yes" console_username="admin" console_passwd="1234" />
  <Entry0 Active="Yes" username="admin"   web_passwd="nE7jA%5m" ... />
  <Entry1 Active="Yes" username="GENEXIS" web_passwd="1234" ... />
  <Entry2 Active="Yes" username="user3"   web_passwd="1234" ... />
</Account>
```

and `/usr/etc/passwd` has `admin:$1$$iC.dUsGpxNNJGeOm1dFio/:0:0:root:/:/bin/sh`,
which is MD5-crypt for `1234`. That is the login for the `utelnetd -l
/bin/login -d` service on port 56090 (`telnet` in `/usr/etc/services`).

If the **bootloader** password itself was changed, no remote path helps: you
need the serial console, and a changed bldr password means a vendor password
recovery procedure or a flash programmer. Keep your own dump and record the
credentials you find.

## 2. Root without the web password: Samba magic script

Works while the **stock vendor firmware** is booted. The share maps to `/` and
runs as root, so a specially named uploaded file is executed as root.

1. Confirm TCP 445 is open: `nc -vz 192.168.1.1 445`. If closed, open
   `http://192.168.1.1/cgi-bin/app-samba.asp` once and press Apply, then wait
   ~30 s.
2. Add `magic script = telnet_start.sh` under `[Samba_Share]` in
   `/etc/samba/smb.conf` (over SMB) — full steps in
   [SAMBA-TELNET.md](SAMBA-TELNET.md).
3. Upload `/tmp/telnet_start.sh` containing:
   ```sh
   #!/bin/sh
   /usr/bin/utelnetd -p 23 -l /bin/sh -d
   ```
4. `telnet 192.168.1.1 23` → root shell with no password.
5. Make it persistent (the port-23 shell itself is not):
   ```sh
   /userfs/bin/tcapi set Account_TelnetEntry Active Yes
   /userfs/bin/tcapi set Account_TelnetEntry telnet_active Yes
   /userfs/bin/tcapi set System_Entry telnet_enable 1
   /userfs/bin/tcapi commit Account_TelnetEntry
   /userfs/bin/tcapi commit System_Entry
   /userfs/bin/tcapi save
   ```
   After reboot, `telnet 192.168.1.1 56090` with `excitel` / MAC.
6. Remove the `magic script` line when done — leaving it is a permanent
   remote-root hole while Samba is on.

The whole thing is scripted: `./tools/samba_telnet.sh 192.168.1.1 admin 1234`.

## 3. UART / bootloader — the last resort

This is what saves you when neither bank boots and no network service answers.
It is **not** needed for a normal install (§5).

- **Settings:** 115200 8N1, **3.3 V TTL logic** (not RS-232). Find the 4-pin
  header (TX, RX, GND, VCC); use a 3.3 V USB-UART adapter.
- Power on and press a key within the **3-second** window, then send `b`.
- Login: `telecomadmin` / `nE7jA%5m`. Prompt: `bldr>`.
- Useful commands: `help`, `imginfo` (shows current image and boot flag).
- Helpers in this kit (need `pyserial`, `/dev/ttyUSB0`, root to open the port):
  ```sh
  python3 tools/bldr_flashargs.py 'imginfo' 'help'
  python3 tools/bldr_set_main_wait.py     # switch boot flag back to main/stock
  ```

If OpenWrt is booting normally, the serial console auto-logs in as root —
there is no `login:` prompt. `tools/serial_cmd.py '<command>'` runs commands
against the `root@OpenWrt:~# ` prompt.

## 4. Boot flag — which bank boots

One byte at absolute flash `0xdfc0000`:

- `0x30` → **main** bank = stock vendor firmware
- `0x31` → **slave** bank = OpenWrt

Read it from a running OpenWrt shell (OpenWrt maps `reservearea` to `mtd9` on
this DTS; check `/proc/mtd`):

```sh
dd if=/dev/mtd9 bs=1 skip=2097152 count=1 2>/dev/null | od -An -tx1
```

Switching direction matters — the bootloader `flash` command does not erase:

- `0x31 → 0x30` (OpenWrt → stock): bit clear only, so bldr works:
  ```
  memwl 80001000 30ffffff
  flash dfc0000 80001000 4 0
  ```
  Then reset/power-cycle. `tools/bldr_set_main_wait.py` does this over serial.
- `0x30 → 0x31` (stock → OpenWrt): bit set, so erase the sector first, from
  stock firmware:
  ```sh
  /userfs/bin/mtd erasesector 2097152 reservearea
  /userfs/bin/mtd writeflash /tmp/flagsec.bin 131072 2097152 reservearea
  ```
  `firmware/flagsec.bin` is a ready 128 KiB sector with `0x31` in byte 0.

If a flash went bad, do **not** erase the other bank. Connect UART, run
`imginfo`, set the flag back to `0x30`, and the stock bank should boot. If both
banks are damaged, restore from your own full dump (§6).

## 5. You do NOT need UART to install OpenWrt

The normal path never touches serial:

- **From stock:** Samba root → telnet on `56090` → `python3 tools/flash_slave_le.py`
  writes the TRX to `tclinux_slave` and the flag to `0x31`, then power-cycle.
- **From a running OpenWrt:** `wget` the TRX, `/tmp/mtdwrite /dev/mtd4 new.trx`,
  `reboot` — no power cycle.

UART is only for recovery (§3). See [OPENWRT-PORT.md](OPENWRT-PORT.md) §5.

## 6. Dump first — your own only

Before changing anything, save both banks and the config partition from the
root shell. This is the only reliable way back if the vendor bank is damaged:

```sh
cat /dev/mtd4  > /tmp/tclinux-main.bin
cat /dev/mtd7  > /tmp/tclinux-slave.bin
cat /dev/mtd1  > /tmp/romfile.bin
cat /dev/mtd11 > /tmp/reservearea.bin
```

Copy them off over SMB. Keep them private: `romfile` contains your MAC, serial
and ISP credentials. Verify a vendor image before flashing with
`python3 tools/t2122a_patch.py --check tclinux-main.bin`.

## 7. Troubleshooting quick table

| Symptom | Fix |
|---|---|
| Web password rejected | Try `excitel`/`exc@123`, then `admin`/MAC; otherwise use Samba or bldr |
| Port 445 closed | Enable Samba under APP → Samba, wait 30 s |
| `NT_STATUS_LOGON_FAILURE` on SMB | Share password is not `1234`; reset Samba in the web UI |
| Port 23 opens then closes | Try `utelnetd -p 23 -l /bin/sh -d -i` or `-l /bin/login` |
| Port 23 not there after reboot | It is one-shot; enable the `56090` service with `tcapi` (§2) |
| Device does not come back after flash | UART → `imginfo` → set flag to `0x30` (§4) |
| OpenWrt boots but no network | Check jump stub, boot flag `0x31`, `lan1/lan2` map, UBIFS overlay — [OPENWRT-PORT.md](OPENWRT-PORT.md) §7 |
| LuCI returns 403 | That is the login page; log in as `root` with the empty password |
| Both banks invalid | Restore your own dump via bldr/`mtd` (§6, [RECOVERY.md](RECOVERY.md) §4) |

## 8. After you get in

- Dump first (§6).
- Change the default web/Samba/telnet passwords or disable the services.
- Remove the `magic script` line from `smb.conf`.
- Do not publish your dump, MAC, serial, Wi-Fi keys or PPPoE credentials.
- Prefer software `reboot` over power-cycling; only power-cycle when switching
  banks in bldr or when the box is unresponsive.
