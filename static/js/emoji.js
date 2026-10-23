// 장소 이모지 (핀·칩·카드 사진 대신 쓰는 타일)
// category는 백엔드 PlaceOut.category 한글명 (예: 한식, 카페/전통찻집, 역사관광지, 휴양관광지, 쇼핑, 축제 …)
const TOUR_RULES = [
  [/역사|궁|고궁|사찰|유적/, '🏯'],
  [/자연|휴양|공원|숲|산/, '🌳'],
  [/쇼핑|시장|백화점|면세/, '🛍️'],
  [/축제|행사|공연/, '🎉'],
  [/박물관|미술관|문화|전시|건축|조형/, '🏛️'],
  [/레포츠|체험/, '🏃'],
];

export function placeEmoji(place) {
  const cat = (place && place.category) || '';
  if (place && place.kind === 'food') {
    return /카페|찻집/.test(cat) ? '☕' : '🍽️';
  }
  for (const [re, e] of TOUR_RULES) if (re.test(cat)) return e;
  return '📍';
}
