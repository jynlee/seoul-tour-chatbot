// 첫 화면 S2a "원형 배지 링" — 시안 first-screen-s2a.html 의 s2a() 를 그대로 옮김.
// 글자 라벨·배·흰 곡선 없음. 한강에는 짧은 물빛 선만.
import { defs, palace, gate, namsan, ddp, b63, lotte, tree, cloud, badge } from './landmarks.js';

const RING_PTS = [[150, 62], [262, 128], [262, 262], [150, 330], [38, 262], [38, 128]];
const RING_ITEMS = [
  [palace, 6, 0.5, '#fff3d9'], [ddp, 4, 0.6, '#e9f1fb'], [lotte, 26, 0.48, '#e9f1fb'],
  [b63, 22, 0.58, '#fff3d9'], [gate, 4, 0.55, '#fbe9e1'], [namsan, 20, 0.44, '#e6f4da'],
];

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

function homePin(x, y, e, c) {
  return '<g class="bob"><circle cx="' + x + '" cy="' + y + '" r="9" fill="' + (c || '#ff9f43') + '" stroke="#fff" stroke-width="2.5"/>'
    + '<text x="' + (x - 5.5) + '" y="' + (y + 4) + '" font-size="10">' + e + '</text></g>';
}

export function homeSvg(s = 'home') {
  return '<svg class="home-art" viewBox="0 0 300 420" aria-hidden="true">' + defs(s)
    + '<rect width="300" height="420" fill="url(#sky' + s + ')"/>'
    + '<circle cx="150" cy="196" r="112" fill="none" stroke="#e3a6b4" stroke-width="2.2" stroke-dasharray="1 7" stroke-linecap="round"/>'
    + '<ellipse cx="150" cy="196" rx="92" ry="78" fill="#e2f1d4"/>'
    + '<path d="M58,196 C88,166 120,214 150,190 C180,166 212,212 242,186 L242,226 C212,250 180,206 150,230 C120,254 88,206 58,236Z" fill="url(#river' + s + ')"/>'
    + '<path d="M76,214 L92,212 M110,224 L122,223 M190,206 L206,204 M214,222 L226,221 M136,206 L146,205" stroke="#e8f6fd" stroke-width="2.4" stroke-linecap="round" opacity=".9"/>'
    + tree(118, 150, 8) + tree(136, 140, 10) + tree(158, 146, 8) + tree(184, 152, 7) + tree(124, 262, 7) + tree(170, 264, 8)
    + ring(s) + homePin(150, 128, '🍜') + cloud(50, 385) + cloud(240, 395)
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
