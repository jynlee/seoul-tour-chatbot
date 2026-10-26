// Q2 화면 시나리오 점검: 헤드리스 Chrome, iPhone 14 Pro(393x852)
// 사용: node run.mjs <shotsDir>   (서버: 8011 정상, 8012 OpenSearch 끔, 8013 Ollama 끔)
import { writeFileSync, mkdirSync } from 'node:fs';
import { launch, newPage, setGeo, sleep } from './cdp.mjs';

const SHOTS = process.argv[2];
mkdirSync(SHOTS, { recursive: true });
// 주소는 환경 변수로 바꿀 수 있음 (QA_OK / QA_OS_DOWN / QA_LLM_DOWN)
const OK = process.env.QA_OK || 'http://localhost:8011';
const OS_DOWN = process.env.QA_OS_DOWN || 'http://localhost:8012';
const LLM_DOWN = process.env.QA_LLM_DOWN || 'http://localhost:8013';

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

async function preparePage(ctx) {
  const p = await newPage(ctx);
  await p.c.send('Page.addScriptToEvaluateOnNewDocument', { source: RECORD_FETCH });
  return p;
}

async function bubbles(p) {
  return p.eval(`[...document.querySelectorAll('#chat .bub')].map(b => ({cls: b.className, text: b.innerText}))`);
}

async function send(p, text, timeout = 90000) {
  const before = (await bubbles(p)).length;
  await p.eval(`(() => { const i = document.querySelector('#msg'); i.value = ${JSON.stringify(text)}; document.querySelector('#inp').requestSubmit(); })()`);
  await p.waitFor(`document.querySelectorAll('#chat .bub').length >= ${before + 2} && !document.querySelector('#chat .typing')`, timeout);
  await sleep(500);
  const sid = await p.eval(`localStorage.getItem('stc.sessionId')`);
  if (sid) sessions.add(sid);
  const all = await bubbles(p);
  return all[all.length - 1];
}

const pins = (p) => p.eval(`[...document.querySelectorAll('#map .pin')].map(b => ({id: b.dataset.id, cls: b.className, title: b.getAttribute('aria-label'), emoji: b.querySelector('.head').innerText}))`);
const lastReq = (p) => p.eval(`(() => { const r = window.__reqs.filter(r => r.url.includes('/api/chat')); return r.length ? JSON.parse(r[r.length-1].body) : null; })()`);
const visible = (p, sel) => p.eval(`(() => { const e = document.querySelector('${sel}'); return !!e && !e.hidden && e.offsetParent !== null; })()`);

const ctx = await launch();
try {
  // ---------------- 1. 첫 화면
  const p = await preparePage(ctx);
  await p.goto(OK + '/');
  await p.shot(`${SHOTS}/01-home.png`);
  const home = await p.eval(`({
    hello: document.querySelector('.hello')?.innerText,
    chips: [...document.querySelectorAll('.home-chip')].map(b => b.innerText),
    svgText: document.querySelectorAll('.home-art text').length,
    resultHidden: document.querySelector('#result').hidden,
    placeholder: document.querySelector('#msg').placeholder,
    hScroll: document.documentElement.scrollWidth > window.innerWidth,
  })`);
  check('1', '첫 화면: 인사말·칩 3개·글자 라벨 없음', home.hello?.includes('안녕하세요') && home.hello?.includes('서울 어디로 떠나볼까요')
    && home.chips.join('|') === '📍 내 주변 맛집|🏯 종로 관광지|☕ 성수 카페' && home.svgText === 0 && home.resultHidden && !home.hScroll,
    JSON.stringify(home));

  // ---------------- 2. 추천 → 핀 색
  const b1 = await send(p, '광화문 근처 맛집 추천해줘');
  await p.shot(`${SHOTS}/02-result-gwanghwamun.png`);
  const pins1 = await pins(p);
  check('2', '추천 → 주황(맛집) 핀 3~5개', b1.cls === 'bub b' && pins1.length >= 3 && pins1.length <= 5 && pins1.every(x => x.cls.includes('food')),
    `핀 ${pins1.length}개: ${pins1.map(x => x.title).join(', ')} / 답변: ${b1.text.slice(0, 60)}`);
  const req1 = await lastReq(p);
  check('2b', '첫 요청 형식(session_id null, location null)', req1 && req1.session_id === null && req1.location === null && req1.message === '광화문 근처 맛집 추천해줘', JSON.stringify(req1));

  // ---------------- 3. 카드 항목 (전화·사진 없는 장소 포함)
  let telMissing = null;
  let cardInfo = null;
  for (const pin of pins1) {
    await p.eval(`document.querySelector('#map .pin[data-id="${pin.id}"]').click()`);
    await sleep(300);
    const info = await p.eval(`(() => { const c = document.querySelector('#card'); return { hidden: c.hidden, text: c.innerText, hasImg: !!c.querySelector('.img img'), tile: c.querySelector('.img span')?.innerText, pinOn: !!document.querySelector('#map .pin.on[data-id="${pin.id}"]') }; })()`);
    if (!cardInfo) { cardInfo = { pin, info }; await p.shot(`${SHOTS}/03-card.png`); }
    if (info.text.includes('전화번호 정보 없음') && !telMissing) { telMissing = { pin, info }; await p.shot(`${SHOTS}/03b-card-no-tel.png`); }
  }
  const ci = cardInfo.info;
  check('3', '카드: 이름·분류·주소·전화·도보·닫기·선택 핀 강조', !ci.hidden && ci.text.includes(cardInfo.pin.title) && ci.text.includes('📍') && ci.text.includes('📞') && ci.text.includes('🚶') && ci.pinOn,
    ci.text.replace(/\n/g, ' / '));
  check('3b', 'Review Focus 4: 전화번호 없는 장소 → "전화번호 정보 없음"', !!telMissing,
    telMissing ? telMissing.pin.title : '이번 추천에 전화번호 없는 장소가 없음(다른 시나리오에서 확인)');
  const noImg = cardInfo.info.hasImg ? null : cardInfo;
  check('3c', 'Review Focus 4: 사진 없는 장소 → 이모지 타일', !noImg || (noImg.info.tile && noImg.info.tile.length > 0),
    `사진 ${ci.hasImg ? '있음' : '없음'}, 타일 ${ci.tile}`);

  // ---------------- 4. "거기 근처" → 핀 교체 (마지막으로 연 카드가 기준)
  const selected = pins1[pins1.length - 1];
  await p.eval(`document.querySelector('#map .pin[data-id="${selected.id}"]').click()`);
  await sleep(300);
  await p.eval(`document.querySelector('#card .x').click()`);
  await sleep(200);
  const b2 = await send(p, '거기 근처 카페 있어?');
  const req2 = await lastReq(p);
  const pins2 = await pins(p);
  await p.shot(`${SHOTS}/04-demonstrative-cafe.png`);
  check('4c', 'QA-2: 답변이 기준점 이름을 씀(LLM 문구)', b2.text.includes(selected.title) || !b2.text.includes('근처'), b2.text);
  check('4', '"거기 근처 카페" → selected_place_id 전송, 카페(☕) 핀으로 교체', req2.selected_place_id === selected.id && pins2.length > 0
    && pins2.every(x => x.emoji.includes('☕')) && pins2.map(x => x.id).join() !== pins1.map(x => x.id).join() && req2.session_id,
    `선택 ${selected.title}(${selected.id}) / 새 핀: ${pins2.map(x => x.title).join(', ')} / 답변: ${b2.text.slice(0, 60)}`);

  // ---------------- 5. 접힘 B안 → 칩 → 카드
  await p.eval(`document.querySelector('#toggle').click()`);
  await sleep(400);
  const fold = await p.eval(`({ fold: document.querySelector('#fold').innerText, chips: [...document.querySelectorAll('#chips .chip')].map(c => c.innerText), mapHidden: document.querySelector('#map').hidden, toggle: document.querySelector('#toggle').innerText })`);
  await p.shot(`${SHOTS}/05-folded.png`);
  check('5', '접힘 B안: 요약 바("○○ 근처 · 추천 N곳")·장소 칩', fold.mapHidden && fold.fold.includes(`${selected.title} 근처`) && fold.fold.includes(`추천 ${pins2.length}곳`) && fold.chips.length === pins2.length,
    JSON.stringify(fold));
  await p.eval(`document.querySelector('#chips .chip').click()`);
  await sleep(300);
  const chipCard = await p.eval(`({ hidden: document.querySelector('#card').hidden, text: document.querySelector('#card').innerText, pressed: !!document.querySelector('#chips .chip[aria-pressed="true"]') })`);
  await p.shot(`${SHOTS}/06-folded-chip-card.png`);
  check('6', '접힘 상태 칩 클릭 → 카드', !chipCard.hidden && chipCard.text.includes(pins2[0].title) && chipCard.pressed, chipCard.text.replace(/\n/g, ' / '));
  await p.eval(`document.querySelector('#fold').click()`);
  await sleep(400);
  check('6b', '요약 바 클릭 → 지도 다시 펼침', await visible(p, '#map'), '');

  // ---------------- 7. 일상 대화 → 지도 유지
  const b3 = await send(p, '고마워!');
  const pins3 = await pins(p);
  await p.shot(`${SHOTS}/07-casual-keeps-map.png`);
  check('7', '"고마워!" → 답변만, 핀 유지', pins3.map(x => x.id).join() === pins2.map(x => x.id).join(), `답변: ${b3.text}`);

  // ---------------- 8. 새로고침 복원
  const beforeReload = await bubbles(p);
  await p.reload();
  await p.waitFor(`document.querySelectorAll('#chat .bub').length > 0`, 15000);
  await sleep(800);
  const afterReload = await bubbles(p);
  const pins4 = await pins(p);
  await p.shot(`${SHOTS}/08-reload-restored.png`);
  check('8', '새로고침 → 대화·핀 복원', afterReload.length === beforeReload.length && pins4.map(x => x.id).join() === pins2.map(x => x.id).join()
    && afterReload.map(b => b.text).join('|') === beforeReload.map(b => b.text).join('|'),
    `말풍선 ${beforeReload.length}→${afterReload.length}, 핀 ${pins4.length}`);
  await p.close();

  // ---------------- 9. GPS 허용
  await setGeo(ctx, OK, 'allow');
  const g = await preparePage(ctx);
  await g.c.send('Emulation.setGeolocationOverride', { latitude: 37.5759, longitude: 126.9769, accuracy: 30 });
  await g.goto(OK + '/');
  await g.eval(`localStorage.clear()`);
  await g.reload();
  const before9 = (await bubbles(g)).length;
  await g.eval(`document.querySelector('.home-chip[data-i="0"]').click()`);
  await g.waitFor(`document.querySelectorAll('#chat .bub').length >= ${before9 + 2} && !document.querySelector('#chat .typing')`, 90000);
  await sleep(600);
  sessions.add(await g.eval(`localStorage.getItem('stc.sessionId')`));
  const req9 = await lastReq(g);
  const gp = await pins(g);
  const me = await g.eval(`!!document.querySelector('#map .me')`);
  await g.shot(`${SHOTS}/09-gps-allowed.png`);
  check('9', 'GPS 허용 → location 전송, 파란 점, 맛집 핀', req9.location && Math.abs(req9.location.lat - 37.5759) < 1e-6 && me && gp.length > 0 && gp.every(x => x.cls.includes('food')),
    `location=${JSON.stringify(req9.location)}, 핀 ${gp.map(x => x.title).join(', ')}`);
  // 📍 버튼: 다음 전송에만 location을 싣고 비움
  await g.eval(`document.querySelector('#gps').click()`);
  await g.waitFor(`document.querySelector('#msg').placeholder.includes('현재 위치 사용 중')`, 10000);
  await g.shot(`${SHOTS}/09b-gps-pending.png`);
  await send(g, '근처 관광지 알려줘');
  const req9b = await lastReq(g);
  await send(g, '맛집 더 알려줘');
  const req9c = await lastReq(g);
  check('9b', '📍 버튼 → 다음 1회만 location, 그 뒤 null', !!req9b.location && req9c.location === null, `${JSON.stringify(req9b.location)} → ${JSON.stringify(req9c.location)}`);
  await g.close();

  // ---------------- 10. GPS 거부 (Review Focus 5)
  await setGeo(ctx, OK, 'deny');
  const d = await preparePage(ctx);
  await d.goto(OK + '/');
  await d.eval(`localStorage.clear()`);
  await d.reload();
  const before10 = (await bubbles(d)).length;
  await d.eval(`document.querySelector('.home-chip[data-i="0"]').click()`);
  await d.waitFor(`document.querySelectorAll('#chat .bub').length >= ${before10 + 3} && !document.querySelector('#chat .typing')`, 90000);
  await sleep(600);
  sessions.add(await d.eval(`localStorage.getItem('stc.sessionId')`));
  const bd = await bubbles(d);
  const req10 = await lastReq(d);
  const meD = await d.eval(`!!document.querySelector('#map .me')`);
  await d.shot(`${SHOTS}/10-gps-denied.png`);
  check('10', 'GPS 거부 → "위치 권한이 없어서…" 말풍선, location null로 계속', bd.some(b => b.text.includes('위치 권한이 없어서 현재 위치를 쓸 수 없어요')) && req10.location === null && !meD,
    bd.map(b => b.text.slice(0, 40)).join(' | '));
  const lastBot = bd[bd.length - 1].text;
  check('10c', 'QA-2: 기준점 없을 때 답변에 "근처/주변" 없음(LLM 문구)', !/근처|주변/.test(lastBot), lastBot);
  // 📍 버튼으로도
  await d.eval(`document.querySelector('#gps').click()`);
  await sleep(1500);
  const bd2 = await bubbles(d);
  check('10b', 'GPS 거부 상태에서 📍 버튼 → 오류 말풍선, 입력창 일반 상태', bd2.length === bd.length + 1 && bd2[bd2.length - 1].text.includes('위치 권한이 없어서')
    && !(await d.eval(`document.querySelector('#msg').placeholder.includes('현재 위치')`)), bd2[bd2.length - 1].text);
  await d.close();

  // ---------------- 11. 첫 질문이 "거기 근처" (Review Focus 3)
  const f = await preparePage(ctx);
  await f.goto(OK + '/');
  await f.eval(`localStorage.clear()`);
  await f.reload();
  const bf = await send(f, '거기 근처 카페 있어?');
  await f.shot(`${SHOTS}/11-demonstrative-first.png`);
  check('11', '첫 질문 "거기 근처 카페 있어?" → 오류 없이 답변', bf.cls === 'bub b', bf.text.slice(0, 80));
  check('11b', 'QA-2: 기준점 없을 때 동네 이름·"근처" 없음(LLM 문구)', !/성수동|근처에/.test(bf.text), bf.text);
  await f.close();

  // ---------------- 12. 서버 오류 말풍선 (Review Focus 2)
  const e = await preparePage(ctx);
  await e.goto(OS_DOWN + '/');
  const be = await send(e, '광화문 근처 맛집 추천해줘', 60000);
  await e.shot(`${SHOTS}/12-server-error.png`);
  check('12', 'OpenSearch 다운 → 오류 말풍선(503 한국어 문구), 앱 계속 사용 가능', be.cls.includes('err') && be.text.includes('검색 서버에 연결할 수 없어요'), be.text);
  const be2 = await send(e, '고마워!', 30000);
  check('12b', '오류 뒤에도 입력·전송 가능', be2.cls === 'bub b', be2.text);
  await e.close();

  // ---------------- 13. Ollama 다운 → 템플릿 답변 (Review Focus 1)
  const l = await preparePage(ctx);
  await l.goto(LLM_DOWN + '/');
  const bl = await send(l, '광화문 근처 맛집 추천해줘', 120000);
  const lp = await pins(l);
  await l.shot(`${SHOTS}/13-llm-down-template.png`);
  check('13', 'Ollama 다운 → 템플릿 답변 + 핀', bl.text.startsWith('광화문 근처 추천 장소를 지도에 표시했어요:') && lp.length >= 3, bl.text);
  await l.close();

  // ---------------- 14. 서버 꺼짐(네트워크 오류)
  const n = await preparePage(ctx);
  await n.goto(OK + '/');
  await n.eval(`localStorage.clear()`);
  await n.reload();
  await n.c.send('Network.enable');
  await n.c.send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  const bn = await send(n, '광화문 근처 맛집', 30000);
  await n.shot(`${SHOTS}/14-network-offline.png`);
  check('14', '네트워크 끊김 → "서버에 연결할 수 없어요" 말풍선', bn.cls.includes('err') && bn.text.includes('서버에 연결할 수 없어요'), bn.text);
  await n.close();
} catch (err) {
  check('X', '실행 오류', false, String(err && err.stack || err));
} finally {
  writeFileSync(`${SHOTS}/results.json`, JSON.stringify({ results, sessions: [...sessions].filter(Boolean) }, null, 2));
  ctx.browser.close();
  ctx.proc.kill();
  const fails = results.filter(r => !r.pass).length;
  console.log(`\n총 ${results.length}개, 실패 ${fails}개`);
}
