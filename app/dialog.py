"""멀티턴 대화 해석: 지칭("두 번째", "아까 그 카페", "거기"), 정보 질문(주차·영업시간…), "다른 데 더".

모두 키워드·규칙 기반 순수 함수. ChatService 가 이 결과로 의도(place_info / 추천)를 고른다.
"""
import re
from dataclasses import dataclass

from app.catalog import CAFE_CAT3, EVENT_TYPE, FOOD_TYPE, Place
from app.center import match_place
from app.intent import ALL_TYPES, TOUR_TYPES, Intent
from app.schemas import HistoryMessage, PlaceOut

# ---- 정보 질문 ----
# detail 키 → 질문 키워드 (scripts/enrich_detail.py 의 공통 키와 같음)
INFO_KEYWORDS: dict[str, tuple[str, ...]] = {
    "parking": ("주차",),
    "hours": ("몇 시", "몇시", "영업", "문 열", "문열", "여는", "닫", "운영 시간", "운영시간", "이용 시간", "이용시간",
              "오픈", "마감"),
    "rest_day": ("쉬는 날", "쉬는날", "휴무", "휴일", "쉬어", "쉬나", "정기휴"),
    "menu": ("메뉴", "뭐가 맛있", "뭐 맛있", "대표 음식", "뭐 팔", "뭘 팔", "파는"),
    "fee": ("가격", "입장료", "요금", "얼마", "무료"),
    "reservation": ("예약",),
    "pet": ("반려", "강아지", "애견", "펫"),
    "stroller": ("유모차",),
    "contact": ("전화", "연락처", "문의"),
    "period": ("기간", "언제까지", "언제 해", "언제 열"),
}
FIELD_LABELS = {
    "parking": "주차", "hours": "이용 시간", "rest_day": "쉬는 날", "menu": "메뉴", "fee": "요금",
    "reservation": "예약", "pet": "반려동물 동반", "stroller": "유모차", "contact": "문의처", "period": "기간",
    "place": "장소", "season": "이용 시기", "discount": "할인", "age": "관람 연령", "packing": "포장",
}
# 지칭된 장소에 대해 설명을 묻는 말
EXPLAIN_KEYWORDS = ("어디야", "어디에", "어디 있", "어디예요", "어디죠", "뭐야", "뭐예요", "뭐하는", "어떤 곳", "어떤곳",
                    "어때", "다시 알려", "다시 말해", "소개", "설명", "자세히")
# 이 말이 있으면 장소 정보 질문이 아니라 추천(기존 near 의도)
NEAR_KEYWORDS = ("근처", "주변", "가까운", "가까이", "추천")
# "다른 데 더 추천해줘" — 직전 지역·카테고리를 이어받고 이미 보여 준 곳은 뺀다
MORE_KEYWORDS = ("다른 데", "다른데", "다른 곳", "다른곳", "더 추천", "더 알려", "또 없", "더 없", "또 추천", "다른 거",
                 "다른거", "더 보여", "딴 데", "딴데")

# ---- 지칭 ----
REF_DEMONSTRATIVES = ("거기", "그곳", "여기", "이곳", "저기", "저곳", "그 집", "그집", "저 집", "그 근처", "그 주변")
REF_MARKERS = ("아까", "방금", "그 ", "저 ")
_ORDINAL_WORD = re.compile(r"(첫|두|둘|세|셋|네|넷|다섯)\s*(?:번\s*)?째")
_ORDINAL_NUM = re.compile(r"(?<!\d)([1-5])\s*번(?!\s*출구)")
_ORDINAL_INDEX = {"첫": 0, "두": 1, "둘": 1, "세": 2, "셋": 2, "네": 3, "넷": 3, "다섯": 4}
# 이름 일부로 찾을 때 무시하는 흔한 말
_STOP_SUBSTRINGS = ("근처", "주변", "맛집", "추천", "알려", "어디", "거기")
# "아까 그 카페" → 분류 일치
_CATEGORY_WORDS = {
    "카페": "카페/전통찻집", "찻집": "카페/전통찻집", "커피": "카페/전통찻집",
    "한식": "한식", "중식": "중식", "중국집": "중식", "일식": "일식", "양식": "양식",
    "박물관": "문화시설", "미술관": "문화시설", "전시": "문화시설", "공원": "휴양관광지",
    "궁": "역사관광지", "쇼핑": "쇼핑", "시장": "쇼핑", "축제": "축제", "공연": "공연/행사",
}
_KIND_WORDS = {"식당": "food", "맛집": "food", "음식점": "food", "밥집": "food", "관광지": "tour", "명소": "tour"}
# 한 글자 분류 단어('궁')는 '궁금'처럼 다른 낱말 속에 흔히 들어간다 → 뒤가 끝·한글 아님·조사일 때만 인정
_PARTICLES = ("은", "는", "이", "가", "을", "를", "에", "도", "만", "로", "으로", "랑", "의", "였")
_HANGUL = re.compile(r"[가-힣]")


def _has(message: str, words) -> bool:
    return any(w in message for w in words)


def _has_word(message: str, word: str) -> bool:
    if len(word) > 1:
        return word in message
    for m in re.finditer(re.escape(word), message):
        rest = message[m.end():]
        if not rest or not _HANGUL.match(rest[0]) or rest.startswith(_PARTICLES):
            return True
    return False


def asked_fields(message: str) -> list[str]:
    return [f for f, words in INFO_KEYWORDS.items() if _has(message, words)]


def is_near(message: str) -> bool:
    return _has(message, NEAR_KEYWORDS)


def is_more_request(message: str) -> bool:
    return _has(message, MORE_KEYWORDS)


def is_explain(message: str) -> bool:
    return _has(message, EXPLAIN_KEYWORDS)


def ordinal_index(message: str) -> int | None:
    if "마지막" in message:
        return -1
    m = _ORDINAL_WORD.search(message)
    if m:
        return _ORDINAL_INDEX[m.group(1)]
    m = _ORDINAL_NUM.search(message)
    if m:
        return int(m.group(1)) - 1
    return None


@dataclass
class Reference:
    place: Place
    kind: str  # ordinal | title | partial | demonstrative


def _longest_title_substring(title: str, message: str) -> int:
    best = 0
    compact = title.replace(" ", "")
    for i in range(len(compact)):
        for j in range(len(compact), i + 1, -1):
            sub = compact[i:j]
            if j - i <= best:
                break
            if sub in message and not any(sub in s for s in _STOP_SUBSTRINGS):
                best = j - i
                break
    return best


def _partial_match(message: str, last_places: list[PlaceOut], use_category: bool) -> PlaceOut | None:
    best, best_score = None, 0
    for p in last_places:
        score = _longest_title_substring(p.title, message)
        score = score if score >= 2 else 0
        if use_category:
            if any(p.category == cat and _has_word(message, w) for w, cat in _CATEGORY_WORDS.items()):
                score = max(score, 2)
            elif any(p.kind == kind and _has_word(message, w) for w, kind in _KIND_WORDS.items()):
                score = max(score, 1)
        if score > best_score:
            best, best_score = p, score
    return best


def resolve_reference(message: str, selected_place_id: str | None, last_places: list[PlaceOut],
                      focus_id: str | None, catalog: dict[str, Place], near: bool = False) -> Reference | None:
    """질문이 가리키는 장소. 순서 > 장소 이름 > '아까 그 ○○' > '거기'(선택한 곳 → 방금 설명한 곳 → 직전 첫 장소)."""
    def from_out(p: PlaceOut | None, kind: str) -> Reference | None:
        if p is not None and p.id in catalog:
            return Reference(catalog[p.id], kind)
        return None

    # 1) 순서: "두 번째", "1번", "마지막"
    idx = ordinal_index(message)
    if idx is not None and last_places and -len(last_places) <= idx < len(last_places):
        return from_out(last_places[idx], "ordinal")

    # 2) 장소 이름: 최근 추천 목록에 있는 이름 우선, 없으면 카탈로그
    in_last = [p for p in last_places if p.title and p.title in message]
    if in_last:
        return from_out(max(in_last, key=lambda p: len(p.title)), "title")
    named = match_place(message, catalog)
    if named is not None:
        return Reference(named, "title")

    # 3) "아까 그 카페", "그 삼계탕집"
    if last_places and _has(message, REF_MARKERS):
        ref = from_out(_partial_match(message, last_places, use_category=not near), "partial")
        if ref is not None:
            return ref

    # 4) "거기/그곳/그 집": 선택한 장소 → 방금 설명한 장소 → 직전 추천의 첫 장소
    if _has(message, REF_DEMONSTRATIVES):
        if selected_place_id:
            chosen = next((p for p in last_places if p.id == selected_place_id), None)
            if chosen is not None:
                return from_out(chosen, "demonstrative")
        if focus_id and focus_id in catalog:
            return Reference(catalog[focus_id], "demonstrative")
        if last_places:
            return from_out(last_places[0], "demonstrative")
    return None


def focus_place_id(messages: list[HistoryMessage], last_places: list[PlaceOut],
                   catalog: dict[str, Place]) -> str | None:
    """마지막 추천 이후 장소 정보 답변(place_info)으로 설명한 장소 id.

    place_info 답변은 places=[]이고 center(source=place, label=장소 이름)만 저장된다.
    """
    for m in reversed(messages):
        if m.role != "assistant":
            continue
        if m.places:
            return None
        c = m.center
        if c is not None and c.source == "place":
            hit = next((p.id for p in last_places if p.title == c.label), None)
            if hit:
                return hit
            hit = next((p.id for p in catalog.values()
                        if p.title == c.label and abs(p.lat - c.lat) < 1e-6 and abs(p.lng - c.lng) < 1e-6), None)
            return hit
    return None


def intent_from_places(places: list[PlaceOut], catalog: dict[str, Place]) -> Intent | None:
    """직전 추천 목록에서 카테고리를 되살린다 (질문에 카테고리가 빠졌을 때 이어받기)."""
    ps = [catalog[p.id] for p in places if p.id in catalog]
    if not ps:
        return None
    types = {p.content_type for p in ps}
    if types == {FOOD_TYPE}:
        cafe = all(p.cat3 == CAFE_CAT3 for p in ps)
        return Intent(content_types={FOOD_TYPE}, cat3=CAFE_CAT3 if cafe else None, casual=False, has_category=True)
    if types == {EVENT_TYPE}:
        return Intent(content_types={EVENT_TYPE}, cat3=None, casual=False, has_category=True)
    if FOOD_TYPE not in types:
        out = set(TOUR_TYPES) | ({EVENT_TYPE} if EVENT_TYPE in types else set())
        return Intent(content_types=out, cat3=None, casual=False, has_category=True)
    out = set(ALL_TYPES) | ({EVENT_TYPE} if EVENT_TYPE in types else set())
    return Intent(content_types=out, cat3=None, casual=False, has_category=True)


def format_history(messages: list[HistoryMessage], limit: int = 8) -> list[str]:
    """프롬프트용 최근 대화 (약 4턴). 봇 턴에는 그때 보여 준 장소 이름을 붙인다."""
    out = []
    for m in messages[-limit:]:
        if m.role == "user":
            out.append(f"사용자: {m.message}")
            continue
        line = f"챗봇: {m.message}"
        if m.places:
            label = m.center.label if m.center else "기준점 없음"
            line += f" [기준점: {label} / 보여 준 장소: {', '.join(p.title for p in m.places)}]"
        elif m.center is not None and m.center.source == "place":
            line += f" [설명한 장소: {m.center.label}]"
        out.append(line)
    return out


def info_value(place: Place, field: str) -> str:
    if field == "contact":
        return place.detail.get("contact") or place.tel
    return place.detail.get(field, "")
