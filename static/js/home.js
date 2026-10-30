// 첫 화면 S2a "원형 배지 링" — 시안 first-screen-s2a.html 의 s2a() 를 그대로 옮김.
// 글자 라벨·배·흰 곡선 없음. 한강에는 짧은 물빛 선만.
// 섬 위 🍜 핀은 사용자 요청으로 뺐다(2026-10-23). 대신 포인터를 따라다니는 🎒 (follower.js).
// 강 위 로고: 로고 시안 D(2026-10-30) — 상단 워드마크와 같은 Jua 두 색, 흰 테두리 글씨.
import { defs, palace, gate, namsan, ddp, b63, lotte, tree, cloud, badge, BADGE_ART } from './landmarks.js';

const RING_PTS = [[150, 62], [262, 128], [262, 262], [150, 330], [38, 262], [38, 128]];
const RING_ITEMS = [
  [palace, 'gyeongbokgung'], [ddp, 'ddp'], [lotte, 'lotte'], [b63, 'b63'], [gate, 'sungnyemun'], [namsan, 'namsan'],
].map(([fn, id]) => [fn, BADGE_ART[id].dy, BADGE_ART[id].k, BADGE_ART[id].col]);

export const HOME_CHIPS = [
  { label: '📍 내 주변 맛집', message: '내 주변 맛집', gps: true },
  { label: '🏯 종로 관광지', message: '종로 관광지 추천해줘' },
  { label: '☕ 성수 카페', message: '성수 카페 추천해줘' },
];

function ring(s) {
  return RING_PTS.map((p, i) => {
    const [fn, dy, k, col] = RING_ITEMS[i];
    return badge(p[0], p[1], 36, fn(p[0], p[1] + dy, k, s), col);
  }).join('');
}

export function homeSvg(s = 'home') {
  return '<svg class="home-art" viewBox="0 0 300 420" aria-hidden="true">' + defs(s)
    + '<rect width="300" height="420" fill="url(#sky' + s + ')"/>'
    + '<circle cx="150" cy="196" r="112" fill="none" stroke="#e3a6b4" stroke-width="2.2" stroke-dasharray="1 7" stroke-linecap="round"/>'
    + '<ellipse cx="150" cy="196" rx="92" ry="78" fill="#e2f1d4"/>'
    + '<path d="M58,196 C88,166 120,214 150,190 C180,166 212,212 242,186 L242,226 C212,250 180,206 150,230 C120,254 88,206 58,236Z" fill="url(#river' + s + ')"/>'
    + '<path d="M76,214 L92,212 M110,224 L122,223 M190,206 L206,204 M214,222 L226,221 M136,206 L146,205" stroke="#e8f6fd" stroke-width="2.4" stroke-linecap="round" opacity=".9"/>'
    + tree(118, 150, 8) + tree(136, 140, 10) + tree(158, 146, 8) + tree(184, 152, 7) + tree(124, 262, 7) + tree(170, 264, 8)
    + '<text class="home-logo" x="150" y="218" font-family="Jua, sans-serif" font-size="30" text-anchor="middle"'
    + ' stroke="#fff" stroke-width="6" stroke-linejoin="round" paint-order="stroke">'
    + '<tspan fill="#ff6f8d">서울</tspan><tspan fill="#5a4632"> 여행친구</tspan></text>'
    + ring(s) + cloud(50, 385) + cloud(240, 395)
    + '</svg>';
}

// onChip(chip) — 칩을 눌렀을 때 호출 ({label, message, gps?})
export function renderHome(el, { onChip } = {}) {
  el.innerHTML = homeSvg()
    + '<div class="hello"><b>안녕하세요! 👋</b>서울 어디로 떠나볼까요?</div>'
    + '<div class="home-chips">'
    + HOME_CHIPS.map((c, i) => '<button type="button" class="home-chip" data-i="' + i + '">' + c.label + '</button>').join('')
    + '</div>';
  el.querySelectorAll('.home-chip').forEach((b) => {
    b.addEventListener('click', () => onChip && onChip(HOME_CHIPS[Number(b.dataset.i)]));
  });
}
