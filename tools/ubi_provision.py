import os, serial, time

HOST = os.environ.get('T2122A_HOST', '192.168.1.10')
s = serial.Serial(os.environ.get('T2122A_SERIAL', '/dev/ttyUSB0'), 115200, timeout=0.05)
LOG = os.environ.get('T2122A_LOG', '/tmp/ubi_provision.log')
f = open(LOG, 'w', buffering=1)


def ru(tok, to):
    d = b''
    end = time.time() + to
    while time.time() < end:
        d += s.read(65536)
        if tok in d:
            break
    return d


def run(cmd, to=90):
    s.reset_input_buffer()
    s.write(cmd.encode() + b'\r')
    d = ru(b'__DONE__', to)
    print('=== %s ===' % cmd, flush=True)
    print(d.decode(errors='replace')[-4000:], flush=True)
    f.write('=== %s ===\n' % cmd)
    f.write(d.decode(errors='replace')[-4000:] + '\n')
    f.flush()


time.sleep(0.2)
s.write(b'\r')
ru(b'# ', 5)

run("wget -O /tmp/rootfs_data.ubifs http://%s:8000/tools/rootfs_data.ubifs; " % HOST +
    "echo WGET=$?; md5sum /tmp/rootfs_data.ubifs; echo __DONE__", 60)
run("ubiformat /dev/mtd7 -y -q; echo FORMAT=$?; echo __DONE__", 120)
run("ubiattach -m 7; echo ATTACH=$?; echo __DONE__", 30)
run("ubimkvol /dev/ubi0 -N rootfs_data -m; echo MKVOL=$?; ubinfo -d 0; echo __DONE__", 30)
run("ubiupdatevol /dev/ubi0_0 /tmp/rootfs_data.ubifs; echo UPD=$?; echo __DONE__", 90)
run("mkdir -p /mnt/t; mount -t ubifs /dev/ubi0_0 /mnt/t; echo MOUNT=$?; "
    "touch /mnt/t/hello; ls -l /mnt/t; umount /mnt/t; echo UMOUNT=$?; echo __DONE__", 30)
f.write('PROVISION DONE\n')
f.close()
s.close()
