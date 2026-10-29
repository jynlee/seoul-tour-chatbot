import { test } from 'node:test';
import assert from 'node:assert/strict';
import { computeBounds, project, mulberry32, seedFor, riverVisible, spreadPins, pinBox, pickLandmarks, landmarkBox } from '../../static/js/map.js';
import { placeEmoji } from '../../static/js/emoji.js';

const W = 400, H = 350;
const GWANGHWAMUN = { lat: 37.5759, lng: 126.9769 };
const PTS = [
  GWANGHWAMUN,
  { lat: 37.5788, lng: 126.9770 }, // 북쪽
  { lat: 37.5744, lng: 126.9858 }, // 동쪽
  { lat: 37.5725, lng: 126.9735 }, // 남서쪽
];

function spanM(b) {
  const lat0 = (b.minLat + b.maxLat) / 2;
  return {
    ns: (b.maxLat - b.minLat) * 111320,
    ew: (b.maxLng - b.minLng) * 111320 * Math.cos(lat0 * Math.PI / 180),
  };
}

test('북쪽 장소는 y가 더 작다', () => {
  const b = computeBounds(PTS);
  const south = project(PTS[3].lat, PTS[3].lng, b, W, H);
  const north = project(PTS[1].lat, PTS[1].lng, b, W, H);
  assert.ok(north.y < south.y);
});

test('동쪽 장소는 x가 더 크다', () => {
  const b = computeBounds(PTS);
  const west = project(PTS[3].lat, PTS[3].lng, b, W, H);
  const east = project(PTS[2].lat, PTS[2].lng, b, W, H);
  assert.ok(east.x > west.x);
});

test('모든 점이 박스 안에 들어온다', () => {
  const b = computeBounds(PTS);
  for (const p of PTS) {
    const { x, y } = project(p.lat, p.lng, b, W, H);
    assert.ok(x >= 0 && x <= W, `x=${x}`);
    assert.ok(y >= 0 && y <= H, `y=${y}`);
  }
});

test('한 점만 있으면 범위가 600m 이상', () => {
  const b = computeBounds([GWANGHWAMUN]);
  const s = spanM(b);
  assert.ok(s.ns >= 599 && s.ew >= 599, JSON.stringify(s));
  const c = project(GWANGHWAMUN.lat, GWANGHWAMUN.lng, b, W, H);
  assert.ok(Math.abs(c.x - W / 2) < 1 && Math.abs(c.y - H / 2) < 1);
});

test('범위 가로세로 비율이 지도 박스(4:3.5)와 같다', () => {
  const s = spanM(computeBounds(PTS));
  assert.ok(Math.abs(s.ew / s.ns - 4 / 3.5) < 0.01, JSON.stringify(s));
});

test('(0,0) 점은 범위에 영향을 주지 않는다', () => {
  const a = computeBounds(PTS);
  const b = computeBounds([...PTS, { lat: 0, lng: 0 }]);
  assert.deepEqual(a, b);
});

test('경도 축에 cos(위도) 보정: 같은 거리면 가로·세로 화면 거리도 같다', () => {
  const b = computeBounds([GWANGHWAMUN]);
  const c = project(GWANGHWAMUN.lat, GWANGHWAMUN.lng, b, W, H);
  const dLat = 100 / 111320; // 북쪽 100m
  const dLng = 100 / (111320 * Math.cos(GWANGHWAMUN.lat * Math.PI / 180)); // 동쪽 100m
  const n = project(GWANGHWAMUN.lat + dLat, GWANGHWAMUN.lng, b, W, H);
  const e = project(GWANGHWAMUN.lat, GWANGHWAMUN.lng + dLng, b, W, H);
  assert.ok(Math.abs((c.y - n.y) - (e.x - c.x)) < 0.5);
});

test('같은 시드는 같은 수열, 다른 시드는 다른 수열', () => {
  const a = mulberry32(42), b = mulberry32(42), c = mulberry32(43);
  const sa = [a(), a(), a()], sb = [b(), b(), b()], sc = [c(), c(), c()];
  assert.deepEqual(sa, sb);
  assert.notDeepEqual(sa, sc);
  for (const v of sa) assert.ok(v >= 0 && v < 1);
});

test('시드는 기준점 좌표로 정해진다', () => {
  assert.equal(seedFor(GWANGHWAMUN), Math.round(37.5759 * 1e4) ^ Math.round(126.9769 * 1e4));
});

test('한강은 범위가 위도 37.505~37.545에 걸칠 때만', () => {
  assert.equal(riverVisible(computeBounds(PTS)), false);
  assert.equal(riverVisible(computeBounds([{ lat: 37.5198, lng: 126.9402 }])), true); // 63빌딩
});

test('겹치는 핀은 서로 밀어내서 겹치지 않게 된다', () => {
  const items = [
    { x: 120, y: 200, lw: 90 },
    { x: 105, y: 222, lw: 120 },
    { x: 300, y: 120, lw: 80 },
  ];
  const out = spreadPins(items);
  const ov = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  assert.equal(ov(pinBox(out[0]), pinBox(out[1])), false);
  assert.deepEqual(out[2], items[2]); // 안 겹친 핀은 그대로
  for (const q of out) assert.ok(q.x >= 0 && q.x <= W && q.y >= 0 && q.y <= H);
});

test('랜드마크는 서로·핀과 겹치면 빼고 고른다', () => {
  const lm = (id, x, y) => ({ l: { id }, x, y });
  const cands = [lm('gyeongbokgung', 200, 175), lm('sungnyemun', 210, 190), lm('namsan', 220, 200), lm('lotte', 360, 300)];
  const pins = [{ x: 360, y: 300, lw: 60 }];
  const out = pickLandmarks(cands, pins);
  assert.deepEqual(out.map((q) => q.l.id), ['gyeongbokgung']); // 가운데 것 하나만, 핀 위 롯데타워는 제외
  const ov = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  for (const q of out) assert.equal(ov(landmarkBox(q), pinBox(pins[0])), false);
});

test('핀 이모지', () => {
  assert.equal(placeEmoji({ kind: 'food', category: '카페/전통찻집' }), '☕');
  assert.equal(placeEmoji({ kind: 'food', category: '한식' }), '🍽️');
  assert.equal(placeEmoji({ kind: 'tour', category: '역사관광지' }), '🏯');
  assert.equal(placeEmoji({ kind: 'tour', category: '휴양관광지' }), '🌳');
  assert.equal(placeEmoji({ kind: 'tour', category: '쇼핑' }), '🛍️');
  assert.equal(placeEmoji({ kind: 'tour', category: '축제' }), '🎉');
  assert.equal(placeEmoji({ kind: 'tour', category: '기타' }), '📍');
});

// ---------- 추천 코스 지도 ----------
import { renderMap } from '../../static/js/map.js';

function mapHtml(opts) {
  const el = { innerHTML: '', querySelectorAll: () => [] };
  renderMap(el, opts);
  return el.innerHTML;
}
const CPLACES = [
  { id: 'a', title: '경복궁', kind: 'tour', lat: 37.5796, lng: 126.977, step: '볼거리' },
  { id: 'b', title: '토속촌', kind: 'food', lat: 37.5780, lng: 126.973, step: '맛집' },
  { id: 'c', title: '커피친구', kind: 'food', lat: 37.5725, lng: 126.9815, step: '카페' },
  { id: 'd', title: '정동전망대', kind: 'tour', lat: 37.5648, lng: 126.9758, step: '야경' },
];

test('코스 지도: 순번 핀 4개 + 순서 점선 path 1개 + 범례', () => {
  const html = mapHtml({ center: null, places: CPLACES });
  const nums = [...html.matchAll(/<span class="head"><span>(\d)<\/span>/g)].map((m) => m[1]).sort();
  assert.deepEqual(nums, ['1', '2', '3', '4']);
  assert.equal((html.match(/data-id=/g) || []).length, 4);
  assert.equal((html.match(/class="course-line"/g) || []).length, 1);
  assert.match(html, /stroke-dasharray="4 5"/);
  assert.match(html, /⋯ 코스 순서/);
});

test('코스 점선은 places 순서대로 이어진다 (M 하나 + L 셋)', () => {
  const html = mapHtml({ center: null, places: CPLACES });
  const d = html.match(/<path class="course-line" d="([^"]+)"/)[1];
  assert.match(d, /^M[\d.]+,[\d.]+( L[\d.]+,[\d.]+){3}$/);
});

test('코스 아닌 지도는 이모지 핀·점선 없음', () => {
  const html = mapHtml({ center: null, places: CPLACES.map(({ step, ...p }) => p) });
  assert.doesNotMatch(html, /course-line|코스 순서/);
  assert.match(html, /<span class="head"><span>(🍽️|📍|[^\d<])/u);
});
