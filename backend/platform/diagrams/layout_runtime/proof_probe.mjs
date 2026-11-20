// Root-installed B1-only hostile workload. Same sandbox as the real ELK entry.
import fs from 'node:fs';
import net from 'node:net';
import dgram from 'node:dgram';
import {spawn} from 'node:child_process';

const chunks = [];
let length = 0;
for await (const chunk of process.stdin) {
  length += chunk.length;
  if (length > 4096) process.exit(79);
  chunks.push(chunk);
}
const request = JSON.parse(Buffer.concat(chunks).toString('utf8'));
if (Object.keys(request).sort().join(',') !== 'mode') process.exit(79);
const mode = request.mode;
if (mode === 'denial') {
  const denied = {};
  const forbidden = process.platform === 'win32'
    ? ['C:\\Users', 'C:\\ProgramData\\StackSense\\Diagrams',
       'C:\\ProgramData\\StackSense\\DiagramSealer']
    : ['/etc/shadow', '/home', '/var/lib/stacksense/diagrams',
       '/opt/stacksense', '/var/run/docker.sock'];
  for (const path of forbidden) {
    try { fs.readdirSync(path); denied[path] = false; }
    catch { try { fs.readFileSync(path); denied[path] = false; } catch { denied[path] = true; } }
  }
  try { fs.writeFileSync(process.platform === 'win32'
    ? 'C:\\Program Files\\StackSense\\DiagramRuntime\\unauthorized' : '/app/unauthorized', 'x'); denied.write = false; }
  catch { denied.write = true; }
  denied.network = await new Promise(resolve => {
    const socket = net.connect({host:'1.1.1.1',port:443});
    socket.once('connect',()=>{socket.destroy();resolve(false);});
    socket.once('error',e=>resolve(['EPERM','EACCES'].includes(e.code)));
    socket.setTimeout(1000,()=>{socket.destroy();resolve(false);});
  });
  denied.udp = await new Promise(resolve => {
    const socket=dgram.createSocket('udp4');
    socket.once('error',e=>{socket.close();resolve(['EPERM','EACCES'].includes(e.code));});
    socket.once('listening',()=>{socket.close();resolve(false);});
    socket.bind(0);
  });
  denied.environment = Object.keys(process.env).every(k=>['LANG','TZ','HOME','NODE_OPTIONS'].includes(k));
  if (process.platform !== 'win32') denied.fds = fs.readdirSync('/proc/self/fd').every(fd=>{
    if (Number(fd)<3) return true;
    try { const target=fs.readlinkSync('/proc/self/fd/'+fd);
      return !target.includes('/home/') && !target.includes('/stacksense/') && !target.includes('socket:');
    } catch { return true; }
  });
  process.stdout.write(JSON.stringify(denied));
} else if (mode === 'cpu' || mode === 'cancel') {
  if (mode === 'cancel') process.stdout.write('STARTED\n');
  while (true) Math.sqrt(Math.random());
} else if (mode === 'memory') {
  const retained=[];
  while (true) { const item=Buffer.alloc(8*1024*1024,0xa5); retained.push(item); }
} else if (mode === 'stdout' || mode === 'stderr') {
  const stream=mode==='stdout'?process.stdout:process.stderr;
  while (true) fs.writeSync(stream.fd,Buffer.alloc(65536,0x61));
} else if (mode === 'fds') {
  const retained=[];
  try {
    while (retained.length < 129) retained.push(fs.openSync(process.platform === 'win32' ? 'NUL' : '/dev/null','r'));
    process.stdout.write(JSON.stringify({code:'LIMIT_NOT_ENFORCED',count:retained.length}));
  }
  catch (e) { process.stdout.write(JSON.stringify({code:e.code,count:retained.length})); }
} else if (mode === 'scratch') {
  const fd=fs.openSync('/tmp/fill','wx'); let bytes=0;
  try { while (true) { fs.writeSync(fd,Buffer.alloc(1024*1024,0x61));bytes+=1024*1024; } }
  catch(e) { process.stdout.write(JSON.stringify({code:e.code,bytes})); }
  finally { fs.closeSync(fd); }
} else if (mode === 'processes') {
  const children=[];
  for (let i=0;i<256;i++) {
    const child=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'ignore'});
    child.on('error',()=>{});children.push(child);
  }
  setInterval(()=>{},1000);
} else process.exit(79);
