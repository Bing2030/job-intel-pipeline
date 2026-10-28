// Create a fresh CDP page target for each URL, capture DOM, then close it.
const url = process.argv[2];
const waitMs = Number(process.argv[3] || 7000);
const port = Number(process.argv[4] || 9226);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function createTarget() {
  for (let i=0;i<20;i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' });
      const t = await r.json();
      if (t.webSocketDebuggerUrl) return t;
    } catch(e) {}
    await sleep(300);
  }
  throw new Error('no target');
}
const target = await createTarget();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej;});
let id=1; const pending=new Map();
ws.onmessage=(ev)=>{const m=JSON.parse(ev.data); if(m.id&&pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id);}};
function send(method,params={}){const i=id++;ws.send(JSON.stringify({id:i,method,params}));return new Promise((res,rej)=>{pending.set(i,m=>m.error?rej(new Error(JSON.stringify(m.error))):res(m.result));setTimeout(()=>{if(pending.has(i)){pending.delete(i);rej(new Error('timeout '+method));}},30000);});}
await send('Page.enable'); await send('Runtime.enable');
const nav=await send('Page.navigate',{url});
await sleep(waitMs);
const loc=await send('Runtime.evaluate',{expression:'location.href',returnByValue:true});
const r=await send('Runtime.evaluate',{expression:'document.documentElement.outerHTML',returnByValue:true});
console.error('NAV', JSON.stringify(nav), 'LOC', JSON.stringify(loc.result));
process.stdout.write(r.result?.value||'');
ws.close();
try { await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`); } catch(e) {}
