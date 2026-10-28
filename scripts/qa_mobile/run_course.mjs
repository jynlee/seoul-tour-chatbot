// 추천 코스 화면 시나리오 점검: 헤드리스 Chrome, iPhone 14 Pro(393x852)
// 사용: node run_course.mjs <shotsDir>   (QA_OK=정상 8012, QA_OS_DOWN=검색 끔 8013, QA_LLM_DOWN=Ollama 끔 8014)
// 끝나면 <shotsDir>/results.json 의 sessions 를 chat_message 에서 지울 것.
import { writeFileSync, mkdirSync } from 'node:fs';
import { launch, newPage, sleep } from './cdp.mjs';

const SHOTS = process.argv[2];
mkdirSync(SHOTS, { recursive: true });
const OK = process.env.QA_OK || 'http://localhost:8012';
const OS_DOWN = process.env.QA_OS_DOWN || 'http://localhost:8013';
const LLM_DOWN = process.env.QA_LLM_DOWN || 'http://localhost:8014';
const TAIL = '영업시간은 가기 전에 한 번 확인해 주세요.';

const results = [];
const sessions = new Set();
function check(id, name, pass, detail = '') {
  results.push({ id, name, pass: !!pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} [${id}] ${name}${detail ? ' — ' + detail : ''}`);
}

async function bubbles(p) {
  return p.eval(`[...document.querySelectorAll('#chat .bub')].map(b => ({cls: b.className, text: b.innerText}))`);
}
async function send(p, text, timeout = 120000) {
  const before = (await bubbles(p)).length;
  await p.eval(`(() => { const i = document.querySelector('#msg'); i.value = ${JSON.stringify(text)}; document.querySelector('#inp').requestSubmit(); })()`);
  await p.waitFor(`document.querySelectorAll('#chat .bub').length >= ${before + 2} && !document.querySelector('#chat .typing')`, timeout);
  await sleep(600);
  const sid = await p.eval(`sessionStorage.getItem('stc.sessionId')`);
  if (sid) sessions.add(sid);
  const all = await bubbles(p);
  return all[all.length - 1];
}
async function fresh(ctx, base) {
  const p = await newPage(ctx);
  await p.goto(base + '/');
  await p.eval(`localStorage.clear(); sessionStorage.clear()`);
  await p.reload();
  return p;
}
const pins = (p) => p.eval(`[...document.querySelectorAll('#map .pin')].map(b => ({id: b.dataset.id, cls: b.className, title: b.getAttribute('aria-label'), head: b.querySelector('.head').innerText.trim()}))`);
const mapInfo = (p) => p.eval(`(() => {
  const line = document.querySelector('#map .course-line');
  return { line: !!line, stroke: line ? getComputedStyle(line).stroke : null, dash: line ? getComputedStyle(line).strokeDasharray : null,
    legend: document.querySelector('#map .legend')?.innerText || '' };
})()`);
const chips = (p) => p.eval(`[...document.querySelectorAll('#chips .chip')].map(c => c.innerText.replace(/\\s+/g, ' ').trim())`);
const sig = (ps) => ps.map(x => x.id).sort().join();
const fold = async (p) => { await p.eval(`document.querySelector('#handle').click()`); await sleep(500); };
const cardOf = (p) => p.eval(`({ hidden: document.querySelector('#card').hidden, step: document.querySelector('#card .step')?.innerText, text: document.querySelector('#card').innerText.replace(/\\n+/g, ' / ') })`);
const clickChip = async (p, i) => { await p.eval(`document.querySelectorAll('#chips .chip')[${i}].click()`); await sleep(400); };

const ctx = await launch();
try {
  // ---- C1 종로 데이트 코스
  const p = await fresh(ctx, OK);
  const b1 = await send(p, '종로 데이트 코스');
  await p.shot(`${SHOTS}/c1-jongno-date-course.png`);
  const pins1 = await pins(p);
  const m1 = await mapInfo(p);
  const n = pins1.length;
  check('C1a', '종로 데이트 코스 → 번호 핀 1..N (3곳 이상)', n >= 3 && pins1.map(x => x.head).sort().join() === Array.from({ length: n }, (_, i) => String(i + 1)).sort().join(), `핀 ${n}: ${pins1.map(x => x.head + x.title).join(', ')}`);
  check('C1b', '갈색 점선 코스 선 + 범례 "⋯ 코스 순서"', m1.line && /122, 106, 88/.test(m1.stroke || '') && m1.dash && m1.dash !== 'none' && m1.legend.includes('⋯ 코스 순서'), JSON.stringify(m1));
  check('C1c', '답 끝 "영업시간은 가기 전에 한 번 확인해 주세요."', b1.text.trim().endsWith(TAIL), b1.text.slice(-80));
  await fold(p);
  const foldText = await p.eval(`document.querySelector('#fold').innerText`);
  const ch = await chips(p);
  await p.shot(`${SHOTS}/c1b-folded.png`);
  check('C1d', `접힘 바 "… · 코스 N곳" + 번호 칩 ${n}개`, new RegExp(`· 코스 ${n}곳`).test(foldText) && ch.length === n && ch.every((c, i) => c.startsWith(String(i + 1))), `${foldText} / ${ch.join(' | ')}`);
  await clickChip(p, 1);
  const card = await cardOf(p);
  await p.shot(`${SHOTS}/c1c-chip2-card.png`);
  check('C1e', '칩 2 → 카드 배지 "2 · {칸}" + "🚶 앞 장소(…)에서 약 N분"', !card.hidden && /^2 · \S+/.test(card.step || '') && /🚶 앞 장소\(.+\)에서 약 \d+분/.test(card.text), card.text);
  const stop2Title = ch[1].replace(/^\d+\s*/, '');

  // ---- C4 후속: 2번 전화번호
  await p.eval(`document.querySelector('#card .x').click()`);
  await p.eval(`document.querySelector('#fold').click()`);
  await sleep(400);
  const before = sig(await pins(p));
  const b4 = await send(p, '2번 거기 전화번호 알려줘');
  const after = sig(await pins(p));
  const m4 = await mapInfo(p);
  await p.shot(`${SHOTS}/c4-phone.png`);
  check('C4a', '"2번 거기 전화번호" → 정보 답, 지도 그대로(핀·코스 선)', before === after && m4.line, `핀 같음=${before === after} / 답: ${b4.text.slice(0, 140)}`);
  check('C4b', '답이 2번 장소 이야기', b4.text.includes(stop2Title), `2번=${stop2Title} / 답: ${b4.text.slice(0, 140)}`);

  // ---- C5 다른 코스
  const first = pins1.map(x => x.title);
  const b5 = await send(p, '다른 코스');
  const pins5 = await pins(p);
  const m5 = await mapInfo(p);
  await p.shot(`${SHOTS}/c5-another-course.png`);
  const rep = pins5.filter(x => first.includes(x.title)).map(x => x.title);
  check('C5', '"다른 코스" → 새 코스(번호·선), 이전 장소 반복 없음', pins5.length >= 3 && pins5.every(x => /^\d$/.test(x.head)) && m5.line && rep.length === 0, `반복 ${rep.join(',') || '없음'} / 핀 ${pins5.map(x => x.head + x.title).join(', ')} / 답: ${b5.text.slice(0, 80)}`);

  // ---- C6 그 근처 카페
  const b6 = await send(p, '그 근처 카페');
  const pins6 = await pins(p);
  const m6 = await mapInfo(p);
  await p.shot(`${SHOTS}/c6-near-cafe.png`);
  check('C6', '"그 근처 카페" → 일반 목록(번호·코스 선 없음)', pins6.length > 0 && pins6.every(x => !/^\d$/.test(x.head)) && !m6.line && !m6.legend.includes('코스'), `핀 ${pins6.map(x => x.head + x.title).join(', ')} / 답: ${b6.text.slice(0, 80)}`);

  // ---- C7 새로고침 복원
  const p7 = await fresh(ctx, OK);
  await send(p7, '종로 데이트 코스');
  const pre = await pins(p7);
  await p7.reload();
  await p7.waitFor(`document.querySelectorAll('#chat .bub').length > 0`, 15000);
  await sleep(1000);
  const post = await pins(p7);
  const m7 = await mapInfo(p7);
  await p7.shot(`${SHOTS}/c7-reload.png`);
  check('C7', '새로고침 → 코스 복원(번호 핀·선·범례)', post.length === pre.length && post.length >= 3 && post.every(x => /^\d$/.test(x.head)) && m7.line && m7.legend.includes('코스 순서') && sig(pre) === sig(post), `핀 ${pre.length}→${post.length} / ${post.map(x => x.head + x.title).join(', ')}`);
  await fold(p7);
  await clickChip(p7, 1);
  const c7 = await cardOf(p7);
  check('C7b', '복원 뒤 칩 2 카드에도 배지·걷기 시간', /^2 · /.test(c7.step || '') && /🚶/.test(c7.text), c7.text);
  await p7.close();

  // ---- C2 명동 쇼핑하고 맛집 코스
  const p2 = await fresh(ctx, OK);
  const b2 = await send(p2, '명동 쇼핑하고 맛집 코스');
  await fold(p2);
  await clickChip(p2, 0);
  const c2 = await cardOf(p2);
  await p2.shot(`${SHOTS}/c2-myeongdong-shopping.png`);
  const pins2 = await pins(p2);
  check('C2', '명동 쇼핑하고 맛집 코스 → 첫 칸 쇼핑', /^1 · 쇼핑/.test(c2.step || '') && pins2.length >= 3, `${c2.text} / 답: ${b2.text.slice(0, 100)}`);
  await p2.close();

  // ---- C3 데이트하기 좋은 카페
  const p3 = await fresh(ctx, OK);
  const b3 = await send(p3, '데이트하기 좋은 카페');
  const pins3 = await pins(p3);
  const m3 = await mapInfo(p3);
  await p3.shot(`${SHOTS}/c3-date-cafe.png`);
  check('C3', '"데이트하기 좋은 카페" → 일반 목록(번호·코스 선 없음)', pins3.length > 0 && pins3.every(x => !/^\d$/.test(x.head)) && !m3.line && !b3.text.includes(TAIL), `핀 ${pins3.map(x => x.head + x.title).join(', ')} / 답: ${b3.text.slice(0, 80)}`);
  await p3.close();

  // ---- C8 여의도 데이트 코스
  const p8 = await fresh(ctx, OK);
  const b8 = await send(p8, '여의도 데이트 코스');
  await fold(p8);
  const ch8 = await chips(p8);
  await p8.shot(`${SHOTS}/c8-yeouido.png`);
  const steps8 = [];
  for (let i = 0; i < ch8.length; i++) { await clickChip(p8, i); steps8.push((await cardOf(p8)).step); }
  check('C8', '여의도 데이트 코스 → 답에 "카페 정보가 적어 코스에서 뺐어요"', b8.text.includes('카페 정보가 적어 코스에서 뺐어요'), `답: ${b8.text}`);
  check('C8b', '여의도 카드 배지에 카페 칸 없음, 3곳 이상', steps8.length >= 3 && steps8.every(s => s && !/카페/.test(s)), `${ch8.join(' | ')} / ${steps8.join(' | ')}`);
  await p8.close();

  // ---- C9 LLM 다운
  const l = await fresh(ctx, LLM_DOWN);
  const bl = await send(l, '종로 데이트 코스', 150000);
  const lp = await pins(l);
  await l.shot(`${SHOTS}/c9-llm-down.png`);
  check('C9', 'Ollama 다운 → "코스를 짜 봤어요: 1." 템플릿 + 번호 핀', bl.text.startsWith('코스를 짜 봤어요: 1.') && lp.length >= 3 && lp.every(x => /^\d$/.test(x.head)), `${bl.text} / 핀 ${lp.length}`);
  await l.close();

  // ---- C10 검색 다운
  const e = await fresh(ctx, OS_DOWN);
  const be = await send(e, '종로 데이트 코스', 60000);
  await e.shot(`${SHOTS}/c10-search-down.png`);
  check('C10', '검색 서버 다운 → 오류 말풍선', be.cls.includes('err') && be.text.includes('검색 서버에 연결할 수 없어요'), be.text);
  await e.close();
} catch (err) {
  check('X', '실행 오류', false, String(err && err.stack || err));
} finally {
  writeFileSync(`${SHOTS}/results.json`, JSON.stringify({ results, sessions: [...sessions].filter(Boolean) }, null, 2));
  ctx.browser.close();
  ctx.proc.kill();
  console.log(`\n총 ${results.length}개, 실패 ${results.filter(r => !r.pass).length}개`);
}
