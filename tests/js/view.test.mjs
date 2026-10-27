import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cardHtml, chipLabel, bubbleHtml, foldBarHtml, placeChipsHtml, placesView } from '../../static/js/view.js';

const GUNG = {
  id: '2786391', title: '개성만두 궁', kind: 'food', category: '한식',
  addr: '서울특별시 종로구 인사동10길 11-3', tel: '02-733-9240', lat: 37.5744, lng: 126.9858,
  image: 'http://tong.visitkorea.or.kr/a.jpg', distance_m: 820, walk_min: 12,
};

test('전화번호·사진이 없으면 "전화번호 정보 없음"과 이모지 타일', () => {
  const html = cardHtml({ ...GUNG, tel: '', image: '' }, { centerLabel: '광화문' });
  assert.match(html, /전화번호 정보 없음/);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /🍽️/);
});

test('카드: 이름·분류·주소·전화·도보 시간', () => {
  const html = cardHtml(GUNG, { centerLabel: '광화문' });
  assert.match(html, /개성만두 궁/);
  assert.match(html, /한식/);
  assert.match(html, /인사동10길 11-3/);
  assert.match(html, /02-733-9240/);
  assert.match(html, /🚶 광화문에서 약 12분/);
  assert.match(html, /<img[^>]+src="http:\/\/tong\.visitkorea\.or\.kr\/a\.jpg"/);
});

test('walk_min이 없으면 도보 줄 생략', () => {
  const html = cardHtml({ ...GUNG, walk_min: null, distance_m: null }, { centerLabel: '광화문' });
  assert.doesNotMatch(html, /🚶/);
});

test('카드는 HTML을 이스케이프한다', () => {
  const html = cardHtml({ ...GUNG, title: '<b>x</b>' });
  assert.doesNotMatch(html, /<b>x<\/b>/);
  assert.match(html, /&lt;b&gt;x/);
});

test('칩 이름: 이모지 + 이름 + 도보 분', () => {
  assert.equal(chipLabel({ title: '광화문 세종클럽', kind: 'food', walk_min: 3 }), '🍽️ 광화문 세종클럽 3분');
  assert.equal(chipLabel({ title: '인사동 찻집', kind: 'food', category: '카페/전통찻집', walk_min: null }), '☕ 인사동 찻집');
  assert.equal(chipLabel({ title: '경복궁', kind: 'tour', category: '역사관광지', walk_min: 0 }), '🏯 경복궁 0분');
});

test('말풍선: 이스케이프, **굵게**, 줄바꿈', () => {
  const html = bubbleHtml('assistant', '<script>x</script> **세종클럽** 추천\n둘째 줄');
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /<b>세종클럽<\/b>/);
  assert.match(html, /<br>/);
  assert.match(bubbleHtml('user', '안녕'), /class="bub u"/);
  assert.match(bubbleHtml('assistant', '안녕'), /class="bub b"/);
  assert.match(bubbleHtml('error', '오류'), /class="bub b err"/);
});

test('접힘 요약 바: "{label} 근처 · 추천 N곳"', () => {
  const html = foldBarHtml({ lat: 37.5759, lng: 126.9769, label: '광화문' }, [GUNG, { ...GUNG, id: '2', kind: 'tour', lat: 37.5788 }]);
  assert.match(html, /<b>광화문 근처<\/b><span> · 추천 2곳<\/span>/);
  assert.match(html, /지도 보기 ▾/);
  assert.equal((html.match(/<i /g) || []).length, 2);
});

test('접힘 요약 바: 구 전체 기준(gu)이면 "근처" 없이 "강서구 · 추천 N곳"', () => {
  const gu = { lat: 37.5509, lng: 126.8495, label: '강서구', source: 'gu' };
  assert.match(foldBarHtml(gu, [GUNG]), /<b>강서구<\/b><span> · 추천 1곳<\/span>/);
  assert.match(foldBarHtml({ ...gu, label: '성수', source: 'area' }, [GUNG]), /<b>성수 근처<\/b>/);
});

test('도보 정보가 null이면(구 전체 기준) 칩·카드에서 도보 표시 숨김', () => {
  const p = { ...GUNG, distance_m: null, walk_min: null };
  assert.equal(chipLabel(p), '🍽️ 개성만두 궁');
  assert.doesNotMatch(cardHtml(p, { centerLabel: '강서구' }), /🚶|약 .*분/);
});

test('접힘 요약 바: 기준점이 없으면 "추천 장소"', () => {
  assert.match(foldBarHtml(null, [GUNG]), /<b>추천 장소<\/b><span> · 추천 1곳<\/span>/);
});

test('장소 칩: 맛집/관광 테두리 클래스와 id', () => {
  const html = placeChipsHtml([GUNG, { ...GUNG, id: 't1', kind: 'tour', title: '경복궁', category: '역사관광지', walk_min: 4 }]);
  assert.match(html, /class="chip food" data-id="2786391"/);
  assert.match(html, /class="chip tour" data-id="t1"/);
  assert.match(html, /🏯 경복궁 4분/);
});

test('지도 펼침: 지도와 바로 아래 "▴ 지도 접기" 손잡이만 보임', () => {
  assert.deepEqual(placesView(true, true), { map: true, handle: true, fold: false, chips: false });
});

test('지도 접힘: 손잡이는 숨고 요약 바·칩이 보임', () => {
  assert.deepEqual(placesView(true, false), { map: false, handle: false, fold: true, chips: true });
});

test('장소가 없으면 지도·손잡이·요약 바·칩 모두 숨김', () => {
  const none = { map: false, handle: false, fold: false, chips: false };
  assert.deepEqual(placesView(false, true), none);
  assert.deepEqual(placesView(false, false), none);
});
