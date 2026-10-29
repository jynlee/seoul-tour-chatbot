// DOM 없이 HTML 문자열을 만드는 순수 함수들 (node --test로 테스트)
// 모양은 시안 result-screen.html(카드·말풍선), result-folded-b.html(요약 바·칩)
import { placeEmoji } from './emoji.js';
import { esc } from './util.js';
import { computeBounds, project } from './map.js';

const hasWalk = (p) => Number.isFinite(p.walk_min);

// 추천 코스인지: 장소에 칸 이름(step)이 하나라도 있으면 코스 (기록 다시 불러오기도 같은 판정)
export function isCourse(places) {
  return (places || []).some((p) => p.step);
}

export function chipLabel(place) {
  return placeEmoji(place) + ' ' + place.title + (hasWalk(place) ? ' ' + place.walk_min + '분' : '');
}

// 정보 카드. centerLabel = 응답 center.label (도보 시간 기준점 이름)
// 코스일 때 index = places 안 순번(0부터), prev = 바로 앞 장소 (첫 곳은 null)
export function cardHtml(place, { centerLabel, index = 0, prev = null } = {}) {
  const food = place.kind === 'food';
  const emoji = placeEmoji(place);
  const img = place.image
    ? '<img src="' + esc(place.image) + '" alt="" loading="lazy" onerror="this.remove()">'
    : '';
  const course = !!place.step;
  const legWalk = Number.isFinite(place.leg_walk_min)
    ? '<div class="row">🚶 ' + (prev ? '앞 장소(' + esc(prev.title) + ')' : esc(centerLabel || '여기')) + '에서 약 ' + place.leg_walk_min + '분</div>'
    : '';
  const walk = course ? legWalk : hasWalk(place)
    ? '<div class="row">🚶 ' + esc(centerLabel || '여기') + '에서 약 ' + place.walk_min + '분</div>'
    : '';
  return '<div class="img ' + (food ? 'food' : 'tour') + '"><span>' + emoji + '</span>' + img + '</div>'
    + '<div class="body"><div class="name"><b>' + esc(place.title) + '</b>'
    + (course ? '<span class="step">' + (index + 1) + ' · ' + esc(place.step) + '</span>' : '')
    + (place.category ? '<span class="tag ' + (food ? 'food' : 'tour') + '">' + esc(place.category) + '</span>' : '') + '</div>'
    + '<div class="row">📍 ' + esc(place.addr || '주소 정보 없음') + '</div>'
    + '<div class="row">📞 ' + (place.tel ? esc(place.tel) : '<span class="none">전화번호 정보 없음</span>') + '</div>'
    + walk + '</div>'
    + '<button type="button" class="x" aria-label="닫기">✕</button>';
}

const reEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// 장소 이름 변형: 그대로 · 앞 대괄호 뗀 이름 · 뒤 괄호 뗀 이름 (띄어쓰기는 뺀 모양, 2글자 이상)
function nameVariants(title) {
  const shown = title.replace(/^\s*\[[^\]]*\]\s*/, '') || title;
  return [title, shown, shown.replace(/\s*\([^()]*\)\s*$/, '')]
    .map((n) => n.replace(/\s/g, ''))
    .filter((n) => n.length >= 2);
}

// 이스케이프된 말풍선 글에서 장소 이름을 **이름** 으로 감싼다. 글자 사이 띄어쓰기 차이("스탈릿 성수")는 봐주고,
// 긴 이름부터 찾으며(성수연방 > 성수), 이미 ** 안인 부분은 건드리지 않는다.
export function markNames(escaped, titles) {
  const names = [...new Set((titles || []).filter(Boolean).flatMap(nameVariants))].sort((a, b) => b.length - a.length);
  if (!names.length) return escaped;
  const pattern = new RegExp(names.map((n) => [...n].map((ch) => reEsc(esc(ch))).join('\\s?')).join('|'), 'g');
  return escaped.split(/(\*\*.+?\*\*)/).map((part, i) => (i % 2 ? part : part.replace(pattern, '**$&**'))).join('');
}

// role: user | assistant | error | typing. names = 굵게 보일 장소 이름들 (답이 말하는 장소)
export function bubbleHtml(role, text, names = []) {
  if (role === 'typing') return '<div class="bub b typing"><i></i><i></i><i></i></div>';
  const cls = role === 'user' ? 'bub u' : role === 'error' ? 'bub b err' : 'bub b';
  let body = esc(text);
  if (role === 'assistant') body = markNames(body, names);
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
  const course = isCourse(places);
  const title = center && center.label ? esc(center.label) + (course || center.source === 'gu' ? '' : ' 근처') : course ? '추천 코스' : '추천 장소';
  const count = course ? (center && center.label ? ' · 코스 ' : ' · ') : ' · 추천 ';
  return '<div class="mini">' + dots + '</div>'
    + '<div class="sum"><b>' + title + '</b><span>' + count + places.length + '곳</span></div>'
    + '<span class="open">지도 보기 ▾</span>';
}

// 장소 영역에서 무엇을 보일지: 펼침 = 지도 + 아래 "▴ 지도 접기" 손잡이, 접힘 = 요약 바 + 칩, 장소 없음 = 모두 숨김
export function placesView(has, mapOpen) {
  return { map: has && mapOpen, handle: has && mapOpen, fold: has && !mapOpen, chips: has && !mapOpen };
}

// 코스 칩: 제목 앞에 색 원 안 순번 (맛집 주황·관광 분홍은 CSS)
export function placeChipsHtml(places, selectedId = null) {
  const course = isCourse(places);
  return places.map((p, i) => '<button type="button" class="chip ' + (p.kind === 'food' ? 'food' : 'tour') + '" data-id="' + esc(p.id) + '"'
    + (p.id === selectedId ? ' aria-pressed="true"' : '') + '>'
    + (course ? '<span class="n circle">' + (i + 1) + '</span>' + esc(p.title) : esc(chipLabel(p))) + '</button>').join('');
}
