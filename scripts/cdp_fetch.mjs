// Minimal CDP fetch: navigate a page and capture outerHTML after a wait.
// Usage: node cdp_fetch.mjs <url> [waitMs] [port]
const url = process.argv[2];
const waitMs = Number(process.argv[3] || 6000);
const port = Number(process.argv[4] || 9223);
if (!url) { console.error('url required'); process.exit(1); }

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function getPageWs() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      let page = list.find(t => t.type === 'page');
      if (!page) {
        const r = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' });
        page = await r.json();
      }
      if (page && page.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch (e) {}
    await sleep(300);
  }
  throw new Error('cannot get CDP page');
}

const wsUrl = await getPageWs();
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let nextId = 1;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
function send(method, params = {}) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((res, rej) => {
    pending.set(id, (m) => m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error('timeout ' + method)); } }, 30000);
  });
}
await send('Page.enable');
await send('Runtime.enable');
const nav = await send('Page.navigate', { url });
console.error('NAV', JSON.stringify(nav));
await sleep(waitMs);
const loc = await send('Runtime.evaluate', { expression: 'location.href', returnByValue: true });
console.error('LOC', JSON.stringify(loc.result));
const r = await send('Runtime.evaluate', { expression: 'document.documentElement.outerHTML', returnByValue: true });
process.stdout.write(r.result.value || '');
ws.close();
