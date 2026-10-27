// 결과 화면 상단 워드마크 왼쪽의 랜드마크 배지 (시안 A)
// 응답 center에서 가장 가까운 6대 랜드마크 하나를 고른다. 거리 제한 없음.
import { LANDMARKS, BADGE_ART, defs, badge } from './landmarks.js';

export const DEFAULT_BADGE = 'gyeongbokgung'; // 광화문

function dist2(a, b) {
  const cos = Math.cos(((a.lat + b.lat) / 2) * Math.PI / 180);
  const dy = a.lat - b.lat, dx = (a.lng - b.lng) * cos;
  return dx * dx + dy * dy;
}

// center가 없거나 좌표가 0이면 직전 배지, 직전도 없으면 광화문
export function pickBadge(center, prevId = null) {
  if (!center || !Number.isFinite(center.lat) || !Number.isFinite(center.lng) || !center.lat || !center.lng) {
    return prevId || DEFAULT_BADGE;
  }
  let best = LANDMARKS[0];
  for (const l of LANDMARKS) if (dist2(center, l) < dist2(center, best)) best = l;
  return best.id;
}

// 40px 배지 SVG. 첫 화면 배지 링과 같은 badge() 모양, 그림은 작은 크기에서도 보이게 키움.
// 낮고 넓은 건물은 더 키우고, 높은 탑은 배지 안에 들어오게 조금만
const ZOOM = { gyeongbokgung: 1.35, sungnyemun: 1.35, ddp: 1.3, namsan: 1.12, b63: 1.12, lotte: 1.12 };
export function badgeSvg(id) {
  const lm = LANDMARKS.find((l) => l.id === id) || LANDMARKS[0];
  const art = BADGE_ART[lm.id];
  const s = 'brand';
  const z = ZOOM[lm.id] || 1.2;
  const inner = '<g clip-path="url(#clip' + s + ')">' + lm.draw(40, 40 + art.dy * z, art.k * z, s) + '</g>';
  return '<svg class="badge-svg" viewBox="0 0 80 80" width="40" height="40" aria-hidden="true">' + defs(s)
    + '<clipPath id="clip' + s + '"><circle cx="40" cy="40" r="32"/></clipPath>'
    + badge(40, 40, 36, inner, art.col) + '</svg>';
}
