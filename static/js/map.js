// 일러스트 지도 — 시안 result-screen.html 스타일
// 크림 바탕 · 숲 덩어리 · 점선 흰 길 · 파스텔 블록 · (한강 근처면) 아래쪽 하늘색 강 · 물방울 핀 + 흰 이름표
// 실제 지도 타일 없음. 핀만 실제 좌표 비율, 배경 장식은 기준점 좌표를 시드로 매번 같게 배치.
// 금지: 초록 박스/격자, 일러스트 위 글자 라벨, 강 위 흰 곡선(배·기러기처럼 보임).
import { LANDMARKS, defs } from './landmarks.js';
import { placeEmoji } from './emoji.js';
import { esc } from './util.js';

export const MAP_W = 400;
export const MAP_H = 350; // 4 : 3.5
const ASPECT = MAP_W / MAP_H;
const M_PER_DEG = 111320;
const RAD = Math.PI / 180;
const DEFAULT_CENTER = { lat: 37.5665, lng: 126.978 }; // 서울시청
// 핀 머리(위)·이름표(아래)가 잘리지 않고 범례(아래, 강이 있으면 위)와 겹치지 않도록 투영할 안쪽 여백
const INSET = { left: 30, right: 30, top: 50, bottom: 56 };
const INSET_RIVER = { left: 30, right: 30, top: 96, bottom: 30 };

const LANDMARK_NEAR_M = 900;

function distanceM(a, b) {
  const cos = Math.cos(((a.lat + b.lat) / 2) * RAD);
  return Math.hypot((a.lat - b.lat) * M_PER_DEG, (a.lng - b.lng) * M_PER_DEG * cos);
}

function valid(p) {
  return p && Number.isFinite(p.lat) && Number.isFinite(p.lng) && p.lat !== 0 && p.lng !== 0;
}

export function computeBounds(points, { minSpanM = 600, pad = 0.15 } = {}) {
  const pts = (points || []).filter(valid);
  if (!pts.length) pts.push(DEFAULT_CENTER);
  let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
  for (const p of pts) {
    minLat = Math.min(minLat, p.lat); maxLat = Math.max(maxLat, p.lat);
    minLng = Math.min(minLng, p.lng); maxLng = Math.max(maxLng, p.lng);
  }
  const cLat = (minLat + maxLat) / 2, cLng = (minLng + maxLng) / 2;
  const cos = Math.cos(cLat * RAD);
  let nsM = Math.max((maxLat - minLat) * M_PER_DEG * (1 + 2 * pad), minSpanM);
  let ewM = Math.max((maxLng - minLng) * M_PER_DEG * cos * (1 + 2 * pad), minSpanM);
  if (ewM / nsM < ASPECT) ewM = nsM * ASPECT; else nsM = ewM / ASPECT;
  const dLat = nsM / 2 / M_PER_DEG, dLng = ewM / 2 / (M_PER_DEG * cos);
  return { minLat: cLat - dLat, maxLat: cLat + dLat, minLng: cLng - dLng, maxLng: cLng + dLng };
}

export function project(lat, lng, bounds, width, height) {
  const cLat = (bounds.minLat + bounds.maxLat) / 2, cLng = (bounds.minLng + bounds.maxLng) / 2;
  const cos = Math.cos(cLat * RAD);
  const spanX = (bounds.maxLng - bounds.minLng) * cos, spanY = bounds.maxLat - bounds.minLat;
  const scale = Math.min(width / spanX, height / spanY);
  return { x: width / 2 + (lng - cLng) * cos * scale, y: height / 2 - (lat - cLat) * scale };
}

export function mulberry32(seed) {
  let a = seed | 0;
  return function () {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function seedFor(center) {
  if (!valid(center)) return 20261023;
  return Math.round(center.lat * 1e4) ^ Math.round(center.lng * 1e4);
}

export function riverVisible(b) {
  return b.minLat <= 37.545 && b.maxLat >= 37.505;
}

// ---------- 배경 ----------
const r1 = (v) => Math.round(v * 10) / 10;

function forest(cx, cy, rx, ry, fill, trees) {
  return '<ellipse cx="' + r1(cx) + '" cy="' + r1(cy) + '" rx="' + r1(rx) + '" ry="' + r1(ry) + '" fill="' + fill + '"/>'
    + trees.map(([x, y, r]) => '<circle cx="' + r1(x) + '" cy="' + r1(y) + '" r="' + r1(r) + '" fill="#8cc271"/>').join('');
}

function road(d, w, dashed) {
  return '<path d="' + d + '" stroke="#fff" stroke-width="' + w + '" fill="none" stroke-linecap="round"/>'
    + (dashed ? '<path d="' + d + '" stroke="#f1e2c2" stroke-width="2" fill="none" stroke-dasharray="7 7"/>' : '');
}

// 한강 윗변 (3차 베지어 제어점)
const RIVER = [[0, MAP_H - 26], [93, MAP_H - 50], [200, MAP_H - 10], [MAP_W, MAP_H - 45]];

function bezier(t, i) {
  const u = 1 - t;
  return u * u * u * RIVER[0][i] + 3 * u * u * t * RIVER[1][i] + 3 * u * t * t * RIVER[2][i] + t * t * t * RIVER[3][i];
}

function riverTopY(x) {
  let lo = 0, hi = 1;
  for (let k = 0; k < 30; k++) {
    const mid = (lo + hi) / 2;
    if (bezier(mid, 0) < x) lo = mid; else hi = mid;
  }
  return bezier((lo + hi) / 2, 1);
}

function overlaps(a, b) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function background(rng, { river, avoid }) {
  const W = MAP_W, H = MAP_H;
  const flip = rng() < 0.5; // 숲 두 덩어리를 어느 대각선에 둘지
  const fx = (x) => (flip ? W - x : x);
  let s = '<rect width="' + W + '" height="' + H + '" fill="#fdf6e3"/>';

  // 큰 숲 (위쪽 모서리) — 시안 (55,18) rx90 ry48 를 400 폭으로
  const k1 = 0.9 + rng() * 0.25;
  s += forest(fx(72), 22, 118 * k1, 62 * k1, '#bfe0a5', [
    [fx(38), 26, 14], [fx(74), 12, 17], [fx(108), 28, 13],
  ]);
  // 작은 숲 (반대쪽 아래 모서리) — 강이 있으면 강 위로 올린다
  const k2 = 0.9 + rng() * 0.25;
  const fy = river ? H - 112 : H - 80;
  s += forest(fx(W - 50), fy, 80 * k2, 45 * k2, '#cfe8b8', [
    [fx(W - 66), fy - 5, 12], [fx(W - 38), fy + 6, 10.5],
  ]);

  // 길: 가로 큰길 1 + 세로 큰길 1 + 구불구불 작은 길 1
  const hy = H * (0.4 + rng() * 0.18), tilt = (rng() - 0.5) * 30;
  const vx = W * (0.28 + rng() * 0.14);
  const cx = W * (0.62 + rng() * 0.12);
  const roads = [
    { x: 0, y: Math.min(hy, hy + tilt) - 10, w: W, h: Math.abs(tilt) + 20 },
    { x: vx - 10, y: 0, w: 30, h: H },
  ];
  s += road('M0,' + r1(hy) + ' L' + W + ',' + r1(hy + tilt), 13, true);
  s += road('M' + r1(vx) + ',0 L' + r1(vx + 10) + ',' + H, 11, true);
  s += road('M' + r1(cx) + ',0 C' + r1(cx + 14) + ',' + r1(H * 0.3) + ' ' + r1(cx - 14) + ',' + r1(H * 0.62) + ' ' + r1(cx + 32) + ',' + H, 7, false);

  // 한강 (아래쪽 띠) — 길 위에 덮어서 길이 강 앞에서 끝나게 하고, 세로 큰길만 다리로 건넌다.
  // 물빛은 S2a와 같은 짧은 직선 (흰 곡선 금지)
  if (river) {
    s += '<path d="M' + RIVER[0][0] + ',' + RIVER[0][1] + ' C' + RIVER.slice(1).map((p) => p[0] + ',' + p[1]).join(' ')
      + ' L' + W + ',' + H + ' L0,' + H + 'Z" fill="#a9dbf3"/>'
      + '<path d="M40,' + (H - 12) + ' L58,' + (H - 13) + ' M150,' + (H - 18) + ' L164,' + (H - 19) + ' M262,' + (H - 16) + ' L280,' + (H - 17) + '" stroke="#e8f6fd" stroke-width="2.6" stroke-linecap="round" opacity=".9"/>';
    const bx = vx + 9, top = riverTopY(bx) - 5;
    s += '<rect x="' + r1(bx - 8) + '" y="' + r1(top + 4) + '" width="18" height="' + r1(H - top) + '" fill="#8fcbe8" opacity=".6"/>'
      + '<rect x="' + r1(bx - 9) + '" y="' + r1(top) + '" width="18" height="' + r1(H - top + 2) + '" rx="2" fill="#fff" stroke="#e6d3b3" stroke-width="1.5"/>'
      + '<path d="M' + r1(bx) + ',' + r1(top + 3) + ' L' + r1(bx) + ',' + H + '" stroke="#f1e2c2" stroke-width="2" stroke-dasharray="7 7"/>';
  }

  // 파스텔 블록: 핀·랜드마크·큰길과 겹치지 않는 자리에만
  const COLORS = ['#f6d6e4', '#e6dcf7', '#fbe3c8'];
  const SIZES = [[72, 45, 13], [61, 43, 12], [53, 40, 11]];
  const placed = [];
  const forests = [
    { x: fx(72) - 118 * k1, y: 0, w: 236 * k1, h: 22 + 62 * k1 },
    { x: fx(W - 50) - 80 * k2, y: fy - 45 * k2, w: 160 * k2, h: 90 * k2 },
  ];
  const blocked = avoid.concat(roads, forests);
  let blocks = '';
  COLORS.forEach((col, i) => {
    const [w, h, rx] = SIZES[i];
    for (let t = 0; t < 40; t++) {
      const b = { x: 10 + rng() * (W - w - 20), y: 10 + rng() * (H - h - (river ? 70 : 20)), w, h };
      const pad = { x: b.x - 6, y: b.y - 6, w: b.w + 12, h: b.h + 12 };
      if (blocked.some((o) => overlaps(pad, o)) || placed.some((o) => overlaps(pad, o))) continue;
      placed.push(b);
      blocks += '<rect x="' + r1(b.x) + '" y="' + r1(b.y) + '" width="' + w + '" height="' + h + '" rx="' + rx + '" fill="' + col + '"/>';
      break;
    }
  });
  return s + blocks;
}

// 핀(머리+이름표) 하나가 차지하는 영역. (x, y) = 물방울 끝 위치.
export function pinBox(q) {
  const half = Math.max(20, q.lw / 2);
  return { x: q.x - half, y: q.y - 46, w: half * 2, h: 64 };
}

export function labelWidth(title) {
  return Math.min(140, [...String(title)].length * 13 + 18);
}

// 겹치는 핀을 서로 조금씩 밀어낸다 (겹친 양이 적은 축으로). 박스 밖으로는 나가지 않는다.
// items: [{x, y, lw}] — 새 배열을 돌려준다.
export function spreadPins(items, { width = MAP_W, height = MAP_H, minY = 50, maxY = height - 22, iterations = 80 } = {}) {
  const out = items.map((q) => ({ ...q }));
  const clamp = (q) => {
    const half = Math.max(20, q.lw / 2);
    q.x = Math.min(Math.max(q.x, half + 4), width - half - 4);
    q.y = Math.min(Math.max(q.y, minY), maxY);
  };
  for (let it = 0; it < iterations; it++) {
    let moved = false;
    for (let i = 0; i < out.length; i++) {
      for (let j = i + 1; j < out.length; j++) {
        const a = pinBox(out[i]), b = pinBox(out[j]);
        if (!overlaps(a, b)) continue;
        const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        if (oy <= ox) {
          const d = (oy / 2 + 1) * (out[i].y <= out[j].y ? -1 : 1);
          out[i].y += d; out[j].y -= d;
        } else {
          const d = (ox / 2 + 1) * (out[i].x <= out[j].x ? -1 : 1);
          out[i].x += d; out[j].x -= d;
        }
        clamp(out[i]); clamp(out[j]);
        moved = true;
      }
    }
    if (!moved) break;
  }
  return out;
}

// 랜드마크 미니 일러스트(배율 0.72)가 차지하는 영역. (x, y) = 건물 바닥 가운데.
const LM_HEIGHT = { gyeongbokgung: 36, sungnyemun: 32, namsan: 80, ddp: 20, b63: 56, lotte: 78 };
export function landmarkBox(q) {
  const h = LM_HEIGHT[q.l.id] || 60;
  return { x: q.x - 36, y: q.y - h, w: 72, h: h + 8 };
}

// 넓은 범위 지도에서 랜드마크끼리·핀과 겹치지 않게 고른다. 지도 가운데에 가까운 것부터.
// pins: [{x, y, lw}] (pinBox 기준)
export function pickLandmarks(cands, pins, { width = MAP_W, height = MAP_H } = {}) {
  const pinBoxes = pins.map((q) => { const b = pinBox(q); return { x: b.x - 6, y: b.y - 6, w: b.w + 12, h: b.h + 12 }; });
  const chosen = [];
  const sorted = [...cands].sort((a, b) => Math.hypot(a.x - width / 2, a.y - height / 2) - Math.hypot(b.x - width / 2, b.y - height / 2));
  for (const q of sorted) {
    const box = landmarkBox(q);
    if (pinBoxes.some((p) => overlaps(box, p))) continue;
    if (chosen.some((c) => overlaps(box, landmarkBox(c)))) continue;
    chosen.push(q);
  }
  return chosen;
}

// ---------- 렌더 ----------
// center: {lat,lng,label}|null, places: PlaceOut[], me: {lat,lng}|null
export function renderMap(el, { center = null, places = [], me = null, selectedId = null, onPinClick } = {}) {
  const W = MAP_W, H = MAP_H;
  const shown = places.filter(valid);
  const course = places.some((p) => p.step); // 추천 코스: 번호 핀 + 순서 점선
  // 기준점 가까이(900m 안)에 6대 랜드마크가 있으면 지도 범위에 넣어서 미니 일러스트가 보이게 한다
  const anchor = valid(center) ? center : shown[0];
  const nearLm = anchor ? LANDMARKS.filter((l) => distanceM(anchor, l) <= LANDMARK_NEAR_M) : [];
  const bounds = computeBounds([...shown, center, me, ...nearLm].filter(Boolean));
  const river = riverVisible(bounds);
  const ins = river ? INSET_RIVER : INSET;
  const iw = W - ins.left - ins.right, ih = H - ins.top - ins.bottom;
  const toXY = (p) => {
    const q = project(p.lat, p.lng, bounds, iw, ih);
    return { x: ins.left + q.x, y: ins.top + q.y };
  };
  const rng = mulberry32(seedFor(center || shown[0] || me));

  const pins = spreadPins(shown.map((p) => ({ p, lw: labelWidth(p.title), ...toXY(p) })), { minY: ins.top, maxY: H - ins.bottom + 4 })
    .sort((a, b) => a.y - b.y);
  const lms = pickLandmarks(
    LANDMARKS.filter((l) => l.lat >= bounds.minLat && l.lat <= bounds.maxLat && l.lng >= bounds.minLng && l.lng <= bounds.maxLng)
      .map((l) => ({ l, ...toXY(l) })),
    pins,
  );
  const avoid = pins.map((q) => ({ x: q.x - 34, y: q.y - 50, w: 68, h: 74 }))
    .concat(lms.map(landmarkBox));

  let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid slice" aria-hidden="true">' + defs('map')
    + background(rng, { river, avoid });
  // 근처 랜드마크 미니 일러스트 (글자 라벨 없음)
  for (const q of lms) svg += q.l.draw(r1(q.x), r1(q.y), 0.72, 'map');

  // 코스 순서 점선: places 순서대로 핀을 잇는다 (SVG라 핀 아래에 깔림)
  if (course) {
    const pts = shown.map((p) => pins.find((q) => q.p === p)).filter(Boolean);
    if (pts.length > 1) {
      svg += '<path class="course-line" d="' + pts.map((q, i) => (i ? 'L' : 'M') + r1(q.x) + ',' + r1(q.y)).join(' ')
        + '" stroke="#7a6a58" stroke-width="2" stroke-dasharray="4 5" fill="none"/>';
    }
  }

  // 선택한 장소까지 걷는 점선
  const sel = pins.find((q) => q.p.id === selectedId);
  let walk = false;
  if (sel && valid(me)) {
    const o = toXY(me);
    if (Math.hypot(o.x - sel.x, o.y - sel.y) > 12) {
      const mx = (o.x + sel.x) / 2 + (sel.y - o.y) * 0.15, my = (o.y + sel.y) / 2 - (sel.x - o.x) * 0.15;
      svg += '<path d="M' + r1(o.x) + ',' + r1(o.y) + ' Q' + r1(mx) + ',' + r1(my) + ' ' + r1(sel.x) + ',' + r1(sel.y) + '" stroke="#7a6a58" stroke-width="2" stroke-dasharray="4 5" fill="none"/>';
      walk = true;
    }
  }
  svg += '</svg>';

  // 밀어내도 이름표끼리 겹치면(핀이 아주 많이 몰린 경우) 순위가 낮은 장소의 이름표만 숨긴다.
  const kept = [];
  const order = [...pins].sort((a, b) => (b.p.id === selectedId) - (a.p.id === selectedId) || shown.indexOf(a.p) - shown.indexOf(b.p));
  for (const q of order) {
    const box = { x: q.x - q.lw / 2, y: q.y - 2, w: q.lw, h: 20 };
    q.hideLbl = kept.some((o) => overlaps(box, o));
    if (!q.hideLbl) kept.push(box);
  }

  const pct = (q) => 'left:' + r1(q.x / W * 100) + '%;top:' + r1(q.y / H * 100) + '%';
  let html = svg;
  if (valid(me)) html += '<div class="me" style="' + pct(toXY(me)) + '"></div>';
  html += pins.map((q) => '<button type="button" class="pin ' + (q.p.kind === 'food' ? 'food' : 'tour') + (q.p.id === selectedId ? ' on' : '') + (q.hideLbl ? ' nolbl' : '')
    + '" data-id="' + esc(q.p.id) + '" style="' + pct(q) + '" aria-label="' + esc(q.p.title) + '">'
    + '<span class="head"><span>' + (course ? places.indexOf(q.p) + 1 : placeEmoji(q.p)) + '</span></span><span class="lbl">' + esc(q.p.title) + '</span></button>').join('');
  html += '<div class="legend' + (river ? ' up' : '') + '">🧡 맛집 · 🩷 관광지 · 🔵 내 위치' + (walk ? ' · ⋯ 걸어서' : '') + (course ? ' · ⋯ 코스 순서' : '') + '</div>';

  el.innerHTML = html;
  el.querySelectorAll('.pin').forEach((b) => {
    b.addEventListener('click', () => onPinClick && onPinClick(b.dataset.id));
  });
}
