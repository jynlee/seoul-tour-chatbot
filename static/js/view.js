// DOM 없이 HTML 문자열을 만드는 순수 함수들 (node --test로 테스트)
// 모양은 시안 result-screen.html(카드·말풍선), result-folded-b.html(요약 바·칩)
import { placeEmoji } from './emoji.js';
import { esc } from './util.js';
import { computeBounds, project } from './map.js';

const hasWalk = (p) => Number.isFinite(p.walk_min);

export function chipLabel(place) {
  return placeEmoji(place) + ' ' + place.title + (hasWalk(place) ? ' ' + place.walk_min + '분' : '');
}

// 정보 카드. centerLabel = 응답 center.label (도보 시간 기준점 이름)
export function cardHtml(place, { centerLabel } = {}) {
  const food = place.kind === 'food';
  const emoji = placeEmoji(place);
  const img = place.image
    ? '<img src="' + esc(place.image) + '" alt="" loading="lazy" onerror="this.remove()">'
    : '';
  const walk = hasWalk(place)
    ? '<div class="row">🚶 ' + esc(centerLabel || '여기') + '에서 약 ' + place.walk_min + '분</div>'
    : '';
  return '<div class="img ' + (food ? 'food' : 'tour') + '"><span>' + emoji + '</span>' + img + '</div>'
    + '<div class="body"><div class="name"><b>' + esc(place.title) + '</b>'
    + (place.category ? '<span class="tag ' + (food ? 'food' : 'tour') + '">' + esc(place.category) + '</span>' : '') + '</div>'
    + '<div class="row">📍 ' + esc(place.addr || '주소 정보 없음') + '</div>'
    + '<div class="row">📞 ' + (place.tel ? esc(place.tel) : '<span class="none">전화번호 정보 없음</span>') + '</div>'
    + walk + '</div>'
    + '<button type="button" class="x" aria-label="닫기">✕</button>';
}

// role: user | assistant | error | typing
export function bubbleHtml(role, text) {
  if (role === 'typing') return '<div class="bub b typing"><i></i><i></i><i></i></div>';
  const cls = role === 'user' ? 'bub u' : role === 'error' ? 'bub b err' : 'bub b';
  let body = esc(text);
  if (role !== 'user') body = body.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  body = body.replace(/\n/g, '<br>');
  return '<div class="' + cls + '">' + body + '</div>';
}

// 접힘(B안) 요약 바: 미니맵 썸네일 + "{label} 근처 · 추천 N곳" + "지도 보기 ▾"
// 구 전체 기준(source 'gu')이면 "근처" 없이 "강서구 · 추천 N곳"
export function foldBarHtml(center, places) {
  const pts = places.filter((p) => p.lat && p.lng);
  const b = computeBounds([...pts, center].filter(Boolean), { minSpanM: 300, pad: 0.1 });
  const dots = pts.map((p) => {
    const q = project(p.lat, p.lng, b, 40, 22);
    return '<i style="left:' + Math.round(q.x + 6) + 'px;top:' + Math.round(q.y + 6) + 'px;background:' + (p.kind === 'food' ? '#ff9f43' : '#ff8fa3') + '"></i>';
  }).join('');
  const title = center && center.label ? esc(center.label) + (center.source === 'gu' ? '' : ' 근처') : '추천 장소';
  return '<div class="mini">' + dots + '</div>'
    + '<div class="sum"><b>' + title + '</b><span> · 추천 ' + places.length + '곳</span></div>'
    + '<span class="open">지도 보기 ▾</span>';
}

// 장소 영역에서 무엇을 보일지: 펼침 = 지도 + 아래 "▴ 지도 접기" 손잡이, 접힘 = 요약 바 + 칩, 장소 없음 = 모두 숨김
export function placesView(has, mapOpen) {
  return { map: has && mapOpen, handle: has && mapOpen, fold: has && !mapOpen, chips: has && !mapOpen };
}

export function placeChipsHtml(places, selectedId = null) {
  return places.map((p) => '<button type="button" class="chip ' + (p.kind === 'food' ? 'food' : 'tour') + '" data-id="' + esc(p.id) + '"'
    + (p.id === selectedId ? ' aria-pressed="true"' : '') + '>' + esc(chipLabel(p)) + '</button>').join('');
}
