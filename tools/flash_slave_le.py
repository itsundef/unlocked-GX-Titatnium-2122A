#!/usr/bin/env python3
"""Flash the LE-corrected OpenWrt slave image from stock firmware.

Run this only while the stock vendor firmware is booted from the main bank. It
downloads the TRX to /tmp on the router, writes it to tclinux_slave, then
rewrites the boot-flag sector to 0x31 with erase + writeflash and verifies both.

The defaults match a stock Excitel unit (telnet 56090, excitel/exc@123). Pass
--host/--user/--password/--url for a different variant. The image is read from
../firmware/openwrt-titanium-slave-le.trx by default.
"""
import argparse, os, socket, time, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--host', default='192.168.1.1')
ap.add_argument('--port', type=int, default=56090)
ap.add_argument('--user', default='excitel')
ap.add_argument('--password', default=os.environ.get('T2122A_PASS', 'exc@123'))
ap.add_argument('--image', default=os.path.join(HERE, '..', 'firmware',
                                                'openwrt-titanium-slave-le.trx'))
ap.add_argument('--url', default='http://192.168.1.10:8000/firmware/openwrt-titanium-slave-le.trx')
ap.add_argument('--flag-url', default='http://192.168.1.10:8000/firmware/flagsec.bin')
args = ap.parse_args()

HOST = args.host
PORT = args.port
USER = args.user
PASS = args.password
IMG_URL = args.url
FLAG_URL = args.flag_url
IMG_SIZE = os.path.getsize(args.image)
print('image: %s (%d bytes)' % (os.path.abspath(args.image), IMG_SIZE), flush=True)

s = socket.create_connection((HOST, PORT), timeout=10)
s.settimeout(0.5)
buf = b''


def read_until(tok, to):
    global buf
    end = time.time() + to
    while time.time() < end:
        if tok in buf:
            i = buf.index(tok) + len(tok)
            out, buf = buf[:i], buf[i:]
            return out
        try:
            c = s.recv(16384)
        except socket.timeout:
            continue
        if not c:
            break
        buf += c
    out, buf = buf, b''
    return out


def run(cmd, to, label=None):
    s.sendall(cmd.encode() + b'\r\n')
    d = read_until(b'# ', to)
    ok = b'# ' in d
    print('### %s | ok=%s' % (label or cmd[:100], ok), flush=True)
    print(d.decode(errors='replace')[-900:], flush=True)
    return ok, d


d = read_until(b'login:', 240)
print('login prompt:', b'login:' in d, flush=True)
if b'login:' not in d:
    print('NO LOGIN PROMPT', flush=True)
    sys.exit(1)
s.sendall(USER.encode() + b'\r\n')
d = read_until(b'Password:', 30)
print('pass prompt:', b'Password' in d, flush=True)
if b'Password' not in d:
    print('NO PASS PROMPT', flush=True)
    sys.exit(1)
s.sendall(PASS.encode() + b'\r\n')
d = read_until(b'# ', 30)
print('shell:', b'# ' in d, flush=True)
if b'# ' not in d:
    print('NO SHELL', flush=True)
    sys.exit(1)

run('echo READY; cat /proc/uptime', 12)
run('/userfs/bin/wget -q -O /tmp/openwrt-slave-le.trx %s; echo WC=$?; ls -l /tmp/openwrt-slave-le.trx'
    % IMG_URL, 120)
run('/userfs/bin/mtd -f write /tmp/openwrt-slave-le.trx %d 0 tclinux_slave; echo FW=$?'
    % IMG_SIZE, 300)
run('sync; echo synced', 20)
run('/userfs/bin/mtd readflash /tmp/hdrchk.bin 4 0 tclinux_slave; echo RD=$?', 30)
run("echo HDR2 > /tmp/hdrref.txt; dd if=/tmp/hdrref.txt of=/tmp/hdrref.bin bs=1 count=4 2>/dev/null; "
    "dd if=/tmp/hdrchk.bin of=/tmp/hdrgot.bin bs=1 count=4 2>/dev/null; "
    "busybox cmp /tmp/hdrref.bin /tmp/hdrgot.bin; echo HDRCMP=$?", 20)
run('/userfs/bin/wget -q -O /tmp/flagsec.bin %s; '
    'echo WFC=$?; ls -l /tmp/flagsec.bin' % FLAG_URL, 60)
run('/userfs/bin/mtd erasesector 2097152 reservearea; echo ER=$?', 90)
run('/userfs/bin/mtd writeflash /tmp/flagsec.bin 131072 2097152 reservearea; echo WF=$?', 120)
run('sync; echo synced', 20)
run('/userfs/bin/mtd readflash /tmp/flagchk.bin 8 2097152 reservearea; echo RD2=$?', 30)
run("echo 1 > /tmp/one.txt; dd if=/tmp/one.txt of=/tmp/one.bin bs=1 count=1 2>/dev/null; "
    "dd if=/tmp/flagchk.bin of=/tmp/f0.bin bs=1 count=1 2>/dev/null; "
    "busybox cmp /tmp/one.bin /tmp/f0.bin; echo FLAGCMP=$?", 20)
print('DONE: require HDRCMP=0 and FLAGCMP=0 before power-cycling.', flush=True)
s.close()
