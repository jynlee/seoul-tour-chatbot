// 최소 CDP 클라이언트 (Node 24 내장 WebSocket/fetch 사용)
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class Conn {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
    this.ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    };
  }
  open() { return new Promise((r, j) => { this.ws.onopen = r; this.ws.onerror = j; }); }
  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((res, rej) => this.pending.set(id, { res, rej }));
  }
  close() { this.ws.close(); }
}

export async function launch(port = 9333) {
  const prof = mkdtempSync(join(tmpdir(), 'qa-chrome-'));
  const proc = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
  let ver;
  for (let i = 0; i < 50; i++) {
    try { ver = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); break; } catch { await sleep(200); }
  }
  const browser = new Conn(ver.webSocketDebuggerUrl);
  await browser.open();
  return { proc, browser, port };
}

export async function newPage({ browser, port }) {
  const t = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const c = new Conn(t.webSocketDebuggerUrl);
  await c.open();
  await c.send('Page.enable');
  await c.send('Runtime.enable');
  // iPhone 14 Pro
  await c.send('Emulation.setDeviceMetricsOverride', { width: 393, height: 852, deviceScaleFactor: 3, mobile: true });
  await c.send('Emulation.setTouchEmulationEnabled', { enabled: true });
  await c.send('Emulation.setUserAgentOverride', {
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  });
  const page = {
    c,
    targetId: t.id,
    async goto(url) { await c.send('Page.navigate', { url }); await page.waitFor('document.readyState === "complete"'); await sleep(600); },
    async reload() { await c.send('Page.reload'); await sleep(300); await page.waitFor('document.readyState === "complete"'); await sleep(1200); },
    async eval(expr) {
      const r = await c.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error('eval 실패: ' + expr + ' → ' + JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails.text));
      return r.result.value;
    },
    async waitFor(expr, timeout = 20000) {
      const t0 = Date.now();
      while (Date.now() - t0 < timeout) {
        try { if (await page.eval(expr)) return true; } catch { /* 로딩 중 */ }
        await sleep(250);
      }
      throw new Error('시간 초과: ' + expr);
    },
    async shot(path) {
      const r = await c.send('Page.captureScreenshot', { format: 'png' });
      writeFileSync(path, Buffer.from(r.data, 'base64'));
    },
    async close() { c.close(); await fetch(`http://127.0.0.1:${port}/json/close/${t.id}`); },
  };
  return page;
}

export async function setGeo({ browser }, origin, mode) {
  if (mode === 'deny') {
    await browser.send('Browser.setPermission', { origin, permission: { name: 'geolocation' }, setting: 'denied' });
  } else {
    await browser.send('Browser.grantPermissions', { origin, permissions: ['geolocation'] });
  }
}

export { sleep };
