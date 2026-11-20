import os, serial, sys, time

s = serial.Serial(os.environ.get('T2122A_SERIAL', '/dev/ttyUSB0'), 115200, timeout=0.05)
PROMPT = b'root@OpenWrt:~# '


def ru(tok, to):
    d = b''
    end = time.time() + to
    while time.time() < end:
        d += s.read(65536)
        if tok in d:
            break
    return d


def run(cmd, to=600):
    s.reset_input_buffer()
    s.write(cmd.encode() + b'\r')
    d = ru(PROMPT, to)
    print('=== %s ===' % cmd, flush=True)
    print(d.decode(errors='replace')[-6000:], flush=True)
    return d


time.sleep(0.2)
s.write(b'\r')
ru(PROMPT, 10)

for cmd in sys.argv[1:]:
    run(cmd)

s.close()
