// B8(장소 정보 질문)·B9(멀티턴) 화면 시나리오 점검: 헤드리스 Chrome, iPhone 14 Pro(393x852)
// 사용: node run_b89.mjs <shotsDir> [baseUrl=http://localhost:8012]
// 끝나면 <shotsDir>/results.json 의 sessions 를 MySQLHistoryRepo.delete_session() 으로 지울 것.
import { writeFileSync, mkdirSync } from 'node:fs';
import { launch, newPage, sleep } from './cdp.mjs';

const SHOTS = process.argv[2];
const BASE = process.argv[3] || 'http://localhost:8012';
mkdirSync(SHOTS, { recursive: true });

const results = [];
const sessions = new Set();
function check(id, name, pass, detail = '') {
  results.push({ id, name, pass: !!pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} [${id}] ${name}${detail ? ' — ' + detail : ''}`);
}

const RECORD_FETCH = `
  window.__reqs = [];
  const _f = window.fetch.bind(window);
  window.fetch = (url, opt = {}) => { window.__reqs.push({ url: String(url), body: opt.body || null }); return _f(url, opt); };
`;

async function freshPage(ctx) {
  const p = await newPage(ctx);
  await p.c.send('Page.addScriptToEvaluateOnNewDocument', { source: RECORD_FETCH });
  await p.goto(BASE + '/');
  await p.eval(`localStorage.clear()`);
  await p.reload();
  return p;
}

const bubbles = (p) => p.eval(`[...document.querySelectorAll('#chat .bub')].map(b => ({cls: b.className, text: b.innerText}))`);
const pins = (p) => p.eval(`[...document.querySelectorAll('#map .pin')].map(b => ({id: b.dataset.id, cls: b.className, title: b.getAttribute('aria-label'), emoji: b.querySelector('.head').innerText}))`);
const lastReq = (p) => p.eval(`(() => { const r = window.__reqs.filter(r => r.url.includes('/api/chat')); return r.length ? JSON.parse(r[r.length-1].body) : null; })()`);
const sid = (p) => p.eval(`localStorage.getItem('stc.sessionId')`);
const ids = (ps) => ps.map((x) => x.id).join();

async function send(p, text, timeout = 120000) {
  const before = (await bubbles(p)).length;
  await p.eval(`(() => { const i = document.querySelector('#msg'); i.value = ${JSON.stringify(text)}; document.querySelector('#inp').requestSubmit(); })()`);
  await p.waitFor(`document.querySelectorAll('#chat .bub').length >= ${before + 2} && !document.querySelector('#chat .typing')`, timeout);
  await sleep(500);
  const s = await sid(p);
  if (s) sessions.add(s);
  const all = await bubbles(p);
  return all[all.length - 1];
}

async function lastBotRecord(p) {
  const s = await sid(p);
  const h = await (await fetch(`${BASE}/api/history/${s}`)).json();
  return h.messages[h.messages.length - 1];
}

// 응답 순서 그대로의 장소 목록 ("두 번째"의 기준). 지도 핀의 DOM 순서는 그리는 순서라 다를 수 있음.
async function apiPlaces(p) {
  const s = await sid(p);
  const h = await (await fetch(`${BASE}/api/history/${s}`)).json();
  const withPlaces = h.messages.filter((m) => m.role === 'assistant' && m.places.length);
  return withPlaces[withPlaces.length - 1].places;
}

// 접힘 상태 장소 칩 이름 (응답 순서와 같아야 함)
async function chipTitles(p) {
  await p.eval(`document.querySelector('#toggle').click()`);
  await sleep(300);
  const t = await p.eval(`[...document.querySelectorAll('#chips .chip')].map(c => c.innerText)`);
  await p.eval(`document.querySelector('#fold').click()`);
  await sleep(300);
  return t;
}

async function foldText(p) {
  await p.eval(`document.querySelector('#toggle').click()`);
  await sleep(300);
  const t = await p.eval(`document.querySelector('#fold').innerText`);
  await p.eval(`document.querySelector('#fold').click()`);
  await sleep(300);
  return t;
}

const ctx = await launch(9334);
try {
  // ---------------- 세션1: 명동
  const p = await freshPage(ctx);
  await send(p, '명동 맛집 추천해줘');
  const m1 = await pins(p);
  const b2 = await send(p, '카페는?');
  const m2 = await pins(p);
  await p.shot(`${SHOTS}/b89-01-myeongdong-cafe.png`);
  check('B9-1', '"카페는?" → 명동 기준 ☕ 핀으로 교체', m2.length > 0 && m2.every((x) => x.emoji.includes('☕')) && ids(m2) !== ids(m1)
    && (await foldText(p)).includes('명동 근처'), `${m2.map((x) => x.title).join(', ')} / ${b2.text.slice(0, 60)}`);

  const b3 = await send(p, '다른 데 더 추천해줘');
  const m3 = await pins(p);
  const fold3 = await foldText(p);
  await p.shot(`${SHOTS}/b89-02-more.png`);
  const overlap = m3.filter((x) => m2.some((y) => y.id === x.id));
  check('B9-2', '"다른 데 더" → 명동 기준·☕ 유지·이전 핀과 안 겹침', m3.length > 0 && m3.every((x) => x.emoji.includes('☕')) && overlap.length === 0 && fold3.includes('명동 근처'),
    `${fold3.replace(/\n/g, ' ')} / ${m3.map((x) => x.title).join(', ')}`);
  check('B9-2b', '"다른 데 더" 답변 지역명 = 명동 (남산 등 다른 지역 없음, 이전 카페 이름 없음)', !b3.text.includes('남산') && !m2.some((x) => b3.text.includes(x.title)), b3.text);

  const a3 = await apiPlaces(p);
  const chips3 = await chipTitles(p);
  check('B9-2c', '접힘 칩 순서 = 응답 순서 ("두 번째"를 화면에서 셀 수 있음)', a3.length === chips3.length && a3.every((x, i) => chips3[i].includes(x.title)), chips3.join(' | '));
  const b4 = await send(p, '두 번째 거기 어디야?');
  const m4 = await pins(p);
  const rec4 = await lastBotRecord(p);
  await p.shot(`${SHOTS}/b89-03-ordinal-info.png`);
  check('B8-1', '"두 번째 거기 어디야?" → 답변만, 핀 그대로, 2번째 장소 설명', ids(m4) === ids(m3) && rec4.center?.label === a3[1]?.title && rec4.places.length === 0,
    `기록 center=${rec4.center?.label} / ${b4.text}`);
  check('B8-1b', '답변이 2번째 장소 이름을 말함(LLM 문구)', b4.text.includes(a3[1]?.title), b4.text);

  const before = await bubbles(p);
  await p.reload();
  await p.waitFor(`document.querySelectorAll('#chat .bub').length > 0`, 15000);
  await sleep(800);
  const after = await bubbles(p);
  const m5 = await pins(p);
  await p.shot(`${SHOTS}/b89-04-reload.png`);
  check('B9-3', '새로고침 → 말풍선 그대로, 핀은 "다른 데 더" 결과로 복원', after.length === before.length && ids(m5) === ids(m3), `말풍선 ${before.length}→${after.length}, 핀 ${m5.length}`);
  await p.close();

  // ---------------- 세션2: 강남
  const g = await freshPage(ctx);
  await send(g, '강남 관광지 알려줘');
  const g1 = await pins(g);
  const foldG = await foldText(g);
  await g.shot(`${SHOTS}/b89-05-gangnam.png`);
  check('B9-4', '"강남 관광지" → 강남구 기준 관광지 핀(장소 \'강남\'이 기준점 아님)', g1.length > 0 && g1.every((x) => x.cls.includes('tour')) && foldG.includes('강남구 근처'),
    `${foldG.replace(/\n/g, ' ')} / ${g1.map((x) => x.title).join(', ')}`);
  const ga1 = await apiPlaces(g);
  const gb2 = await send(g, '아까 첫 번째 거 다시 알려줘');
  const g2 = await pins(g);
  const recG = await lastBotRecord(g);
  check('B8-2', '"아까 첫 번째 거 다시 알려줘" → 1번 장소 설명, 핀 그대로', ids(g2) === ids(g1) && recG.center?.label === ga1[0].title, `${recG.center?.label} / ${gb2.text}`);
  const gb3 = await send(g, '거기서 가까운 맛집은?');
  const g3 = await pins(g);
  const foldG3 = await foldText(g);
  await g.shot(`${SHOTS}/b89-06-gangnam-near-food.png`);
  check('B9-5', '"거기서 가까운 맛집은?" → 1번 장소 기준 맛집 핀', g3.length > 0 && g3.every((x) => x.cls.includes('food')) && foldG3.includes(`${ga1[0].title} 근처`),
    `${foldG3.replace(/\n/g, ' ')} / ${gb3.text.slice(0, 60)}`);
  await g.close();

  // ---------------- 정보 질문
  const q = await freshPage(ctx);
  await send(q, '명동 맛집 추천해줘');
  const q1 = await pins(q);
  const qb = await send(q, '각시보쌈 주차 가능해?');  // B7 574/574 기준 주차 정보 없는 음식점
  await q.shot(`${SHOTS}/b89-07-info-missing.png`);
  check('B8-3', '이름으로 정보 질문, 정보 없음 → 지어내지 않고 전화 안내, 핀 그대로',
    /^각시보쌈 — 주차 정보는 없어요\. 전화\(.+\)로 확인해 보세요\.$/.test(qb.text) && ids(await pins(q)) === ids(q1), qb.text);

  const chosen = q1[q1.length - 1];
  await q.eval(`document.querySelector('#map .pin[data-id="${chosen.id}"]').click()`);
  await sleep(300);
  await q.eval(`document.querySelector('#card .x').click()`);
  await sleep(200);
  const qb2 = await send(q, '거기 전화번호 알려줘');
  const req = await lastReq(q);
  const recQ = await lastBotRecord(q);
  await q.shot(`${SHOTS}/b89-08-info-selected.png`);
  check('B8-4', '핀 선택 후 "거기 전화번호" → selected_place_id 전송, 그 장소 설명', req.selected_place_id === chosen.id && recQ.center?.label === chosen.title && ids(await pins(q)) === ids(q1),
    `${chosen.title} / ${qb2.text}`);

  const qb3 = await send(q, '거기 근처 카페 있어?');
  const q3 = await pins(q);
  const foldQ = await foldText(q);
  await q.shot(`${SHOTS}/b89-09-near-cafe.png`);
  check('B9-6', '회귀: 정보 질문 뒤 "거기 근처 카페" → 그 장소 기준 ☕ 핀', q3.length > 0 && q3.every((x) => x.emoji.includes('☕')) && foldQ.includes(`${chosen.title} 근처`),
    `${foldQ.replace(/\n/g, ' ')} / ${qb3.text.slice(0, 60)}`);
  await q.close();

  // ---------------- QA-4·QA-5 재확인
  const k = await freshPage(ctx);
  await send(k, '종로 역사 관광지');
  const ka = await apiPlaces(k);
  const kp = await pins(k);
  const palace = ka.find((x) => x.title.includes('궁'));
  const kb = await send(k, '아까 그 궁 주차돼?');
  const recK = await lastBotRecord(k);
  check('QA-4', '"아까 그 궁" → 이름에 "궁"이 든 장소, 핀 그대로', palace && recK.center?.label === palace.title && ids(await pins(k)) === ids(kp),
    `목록 ${ka.map((x) => x.title).join(', ')} / 설명 ${recK.center?.label} / ${kb.text}`);
  const kb2 = await send(k, `${ka.length + 1}번째 거 어디야?`);
  await k.shot(`${SHOTS}/b89-11-out-of-range.png`);
  check('QA-5', '목록 범위 밖 순서 → "목록에는 N곳까지 있어요" 말풍선, 핀 그대로', kb2.text.startsWith(`목록에는 ${ka.length}곳까지 있어요`) && ids(await pins(k)) === ids(kp), kb2.text);
  await k.close();

  // ---------------- QA-6: 가리킬 장소 없는 "거기 어디야?"
  const z = await freshPage(ctx);
  const zb = await send(z, '거기 어디야?');
  check('QA-6', '첫 메시지 "거기 어디야?" → 되묻기, 핀 없음', zb.text.includes('어느 곳을 말씀하시는지') && (await pins(z)).length === 0, zb.text);
  await z.close();

  // ---------------- 구 전체·산책 주제 (51b8c0d)
  const w = await freshPage(ctx);
  const wb = await send(w, '강서구 공원 추천해줘');
  const wa = await apiPlaces(w);
  const wchips = await chipTitles(w);
  const foldW = await foldText(w);
  await w.eval(`document.querySelector('#map .pin[data-id="${wa[0].id}"]').click()`);
  await sleep(300);
  const wcard = await w.eval(`document.querySelector('#card').innerText`);
  await w.shot(`${SHOTS}/b89-12-gu-park.png`);
  check('GU-1', '"강서구 공원 추천해줘" → 강서구 기준, 1번 칩·핀이 강서습지생태공원', wa[0]?.title === '강서습지생태공원' && wchips[0]?.includes('강서습지생태공원') && foldW.includes('강서구'),
    `${foldW.replace(/\n/g, ' ')} / ${wchips.join(' | ')} / 카드: ${wcard.replace(/\n/g, ' / ')} / ${wb.text}`);
  const wb2 = await send(w, '금천구 산책할 곳');
  await w.shot(`${SHOTS}/b89-13-topic-missing.png`);
  check('GU-2', '"금천구 산책할 곳" → 맞는 곳이 없다고 솔직히 안내 + 핀', /없|못 찾|어려|아쉽/.test(wb2.text) && (await pins(w)).length > 0, wb2.text);
  await w.close();

  // ---------------- 대상 없음 → 되묻기
  const c = await freshPage(ctx);
  const cb = await send(c, '주차 가능해?');
  await c.shot(`${SHOTS}/b89-10-clarify.png`);
  check('B8-5', '대상 없는 정보 질문 → 되묻기, 오류 말풍선 아님, 핀 없음', cb.cls === 'bub b' && cb.text.includes('어느 곳을 말씀하시는지') && (await pins(c)).length === 0, cb.text);
  await c.close();
} catch (err) {
  check('X', '실행 오류', false, String((err && err.stack) || err));
} finally {
  writeFileSync(`${SHOTS}/results.json`, JSON.stringify({ results, sessions: [...sessions].filter(Boolean) }, null, 2));
  ctx.browser.close();
  ctx.proc.kill();
  const fails = results.filter((r) => !r.pass).length;
  console.log(`\n총 ${results.length}개, 실패 ${fails}개`);
}
