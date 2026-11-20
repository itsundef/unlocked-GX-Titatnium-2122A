#!/usr/bin/env python3
import os, serial, time, sys
PORT=os.environ.get('T2122A_SERIAL','/dev/ttyUSB0'); LOG=os.environ.get('T2122A_LOG','/tmp/bldr_flashargs.log')
cmds=sys.argv[1:] or []
s=serial.Serial(PORT,115200,timeout=0.15); f=open(LOG,'w',buffering=1)
def wf(t,to):
 d=b''; e=time.time()+to
 while time.time()<e:
  d+=s.read(4096)
  if t in d: break
 return d
buf=wf(b'Press any key in 3 secs',60)
s.write(b'b'); wf(b'UserName:',5)
s.write(b'telecomadmin\r'); wf(b'Password:',2)
s.write(b'nE7jA%5m\r'); buf=wf(b'bldr>',5)
f.write('login: '+str(b'bldr>' in buf)+'\n')
for c in cmds:
 s.write(c.encode()+b'\r'); time.sleep(0.8)
 out=b''; e=time.time()+3
 while time.time()<e: out+=s.read(4096)
 f.write(f'--- {c} ---\n'+out.decode(errors='replace')+'\n')
f.close(); s.close(); print('done')
