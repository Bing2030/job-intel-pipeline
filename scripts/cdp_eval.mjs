// Evaluate an async expression in the current CDP page and print result.
const port = Number(process.env.CDP_PORT || 9223);
const expr = process.argv[2];
if (!expr) { console.error('expr required'); process.exit(1); }
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function wsUrl() {
  for (let i=0;i<20;i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find(t=>t.type==='page');
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch(e) {}
    await sleep(300);
  }
  throw new Error('no page');
}
const ws = new WebSocket(await wsUrl());
await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej;});
let id=1; const pending=new Map();
ws.onmessage=(ev)=>{const m=JSON.parse(ev.data); if(m.id&&pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id);}};
function send(method,params={}){const i=id++;ws.send(JSON.stringify({id:i,method,params}));return new Promise((res,rej)=>{pending.set(i,m=>m.error?rej(new Error(JSON.stringify(m.error))):res(m.result));setTimeout(()=>{if(pending.has(i)){pending.delete(i);rej(new Error('timeout '+method));}},30000);});}
await send('Runtime.enable');
const r = await send('Runtime.evaluate',{expression:expr,awaitPromise:true,returnByValue:true});
console.log(JSON.stringify(r.result?.value ?? r));
ws.close();
