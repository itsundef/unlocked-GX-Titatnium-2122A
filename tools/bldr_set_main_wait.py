#!/usr/bin/env python3
"""Power-on hook: enter bldr, set boot flag back to main (0x30), show help.

0x31 -> 0x30 only clears bit 0, so the bootloader's non-erasing flash write
works for this direction. A reset is still needed for it to take effect.
"""
import os, serial, time, sys

PORT = os.environ.get('T2122A_SERIAL', '/dev/ttyUSB0')
LOG = os.environ.get('T2122A_LOG', '/tmp/bldr_set_main.log')
s = serial.Serial(PORT, 115200, timeout=0.05)
f = open(LOG, 'w', buffering=1)

def read_until(tok, to):
    d = b''
    end = time.time() + to
    while time.time() < end:
        d += s.read(65536)
        if tok in d:
            break
    return d

def send(c, wait=2.0):
    s.reset_input_buffer()
    s.write(c.encode() + b'\r')
    d = read_until(b'bldr>', wait)
    f.write('--- %s ---\n' % c + d.decode(errors='replace') + '\n')
    f.flush()
    return d

f.write('waiting for boot prompt...\n')
d = read_until(b'Press any key in 3 secs', 900)
f.write(d.decode(errors='replace')[-2500:])
if b'Press any key in 3 secs' not in d:
    f.write('\nNO BOOT PROMPT\n')
    f.close(); s.close(); sys.exit(1)
time.sleep(0.05)
s.write(b'b')                      # exactly one b
d = read_until(b'UserName:', 10)
if b'UserName:' in d:
    s.write(b'telecomadmin\r')
    read_until(b'Password:', 4)
    s.write(b'nE7jA%5m\r')
    d = read_until(b'bldr>', 8)
f.write('\nLOGIN TAIL:\n' + d.decode(errors='replace')[-500:] + '\n')
if b'bldr>' not in d:
    f.write('LOGIN FAILED\n')
    f.close(); s.close(); sys.exit(1)

s.reset_input_buffer()
send('imginfo', 3)
send('memwl 80001000 30ffffff', 1)
send('flash dfc0000 80001000 4 0', 6)
send('imginfo', 3)
send('help', 5)
f.write('DONE: flag written 0x30; power-cycle to boot main.\n')
f.close(); s.close()
print('done')
