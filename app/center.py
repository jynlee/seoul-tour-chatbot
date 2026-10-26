""""근처"의 기준점 결정 (spec §5.2).

우선순위: ① GPS ② 지시어("거기 근처")→방금 추천한 장소 ③ 카탈로그 장소명 ④ 인기 지역 이름표
⑤ 주소의 동 이름 ⑥ 구 이름(“종로”처럼 '구'를 뗀 이름도) ⑦ 직전 기준점 ⑧ 없음.
"""
import re
from dataclasses import dataclass

from app.catalog import Place, has_coords
from app.geo import AREAS, SEOUL_GU
from app.schemas import CenterOut, Location, PlaceOut

DEMONSTRATIVES = ("거기 근처", "그 근처", "그 주변", "거기", "그곳", "저기")

_DONG = re.compile(r"^([가-힣]+동)(?:\d+가)?$")

# 2글자 장소명('기후'·'길목'·'기와')은 일반 단어와 겹친다 → 질문 전체가 그 이름이거나,
# 이름 바로 뒤에 장소로 쓰였다는 말이 올 때만 장소로 인정 ("기후 맛집", "길목에서 가까운", "구펠 주차 돼?").
SHORT_TITLE_LEN = 2
_PLACE_USAGE = ("근처", "주변", "가까운", "가까이", "맛집", "카페", "식당", "에서", "까지", "가는", "어디", "위치",
                "주차", "영업", "메뉴", "전화", "몇 시", "몇시", "휴무", "가격", "예약")
_PARTICLE = re.compile(r"^(?:은|는|이|가|도)\s*")
_HANGUL = re.compile(r"[가-힣]")
_TRIM = re.compile(r"[\s?!.~,]+")


@dataclass
class Center:
    lat: float
    lng: float
    label: str
    source: str  # gps | place | area | gu | history
    place_id: str | None = None  # source=place 일 때 그 장소 id (추천 결과에서 자기 자신은 뺌)

    def to_out(self) -> CenterOut:
        return CenterOut(lat=self.lat, lng=self.lng, label=self.label, source=self.source)


def _gu_aliases() -> list[tuple[str, str]]:
    """(질문에서 찾을 이름, 구 이름). '종로'처럼 구를 뗀 이름은 두 글자 이상일 때만."""
    aliases = [(gu, gu) for gu in SEOUL_GU]
    aliases += [(gu[:-1], gu) for gu in SEOUL_GU if len(gu[:-1]) >= 2]
    return sorted(aliases, key=lambda a: -len(a[0]))


GU_ALIASES = _gu_aliases()


def dong_names(addr: str) -> set[str]:
    names = set()
    for token in re.split(r"[\s(),]+", addr):
        m = _DONG.match(token)
        if m and len(m.group(1)) >= 2:
            names.add(m.group(1))
    return names


def _dong_index(catalog: dict[str, Place]) -> dict[str, list[Place]]:
    index: dict[str, list[Place]] = {}
    for p in catalog.values():
        if not has_coords(p):
            continue
        for name in dong_names(p.addr):
            index.setdefault(name, []).append(p)
    return index


def _mean_center(places: list[Place], label: str, source: str) -> Center:
    lat = sum(p.lat for p in places) / len(places)
    lng = sum(p.lng for p in places) / len(places)
    return Center(lat=lat, lng=lng, label=label, source=source)


def _match_area(message: str) -> str | None:
    hits = [name for name in AREAS if name in message]
    return max(hits, key=len) if hits else None


def _match_gu(message: str) -> str | None:
    for alias, gu in GU_ALIASES:
        if alias in message:
            return gu
    return None


def _match_gu_alias(message: str) -> str | None:
    for alias, _gu in GU_ALIASES:
        if alias in message:
            return alias
    return None


def _short_title_used_as_place(title: str, text: str) -> bool:
    if _TRIM.sub("", text) == title.replace(" ", ""):
        return True
    for m in re.finditer(re.escape(title), text):
        if m.start() > 0 and _HANGUL.match(text[m.start() - 1]):
            continue  # '골목길목'처럼 다른 단어의 일부
        rest = text[m.end():].lstrip()
        rest = rest if rest.startswith(_PLACE_USAGE) else _PARTICLE.sub("", rest)
        if rest.startswith(_PLACE_USAGE):
            return True
    return False


def _match_place(message: str, catalog: dict[str, Place]) -> Place | None:
    """카탈로그 제목이 질문에 포함되면: 정확히 같은 제목 > 가장 긴 제목 > 가장 짧은 id."""
    text = message.strip()
    # 지역·구 이름과 같거나 그 안에 들어 있는 제목(예: '강남'=강남구, '강남역' 속 '강남')은 장소로 보지 않는다.
    # → 구/지역 이름이 같은 이름의 장소보다 우선.
    bigger_names = [n for n in AREAS if n in text]
    alias = _match_gu_alias(text)
    if alias:
        bigger_names.append(alias)
    candidates = []
    for p in catalog.values():
        if not p.title or not has_coords(p) or p.title not in text:
            continue
        if any(p.title in n for n in bigger_names):
            continue
        if len(p.title.replace(" ", "")) <= SHORT_TITLE_LEN and not _short_title_used_as_place(p.title, text):
            continue
        candidates.append(p)
    if not candidates:
        return None
    return min(candidates, key=lambda p: (p.title != text, -len(p.title), len(p.id), p.id))


def _match_dong(message: str, catalog: dict[str, Place]) -> tuple[str, list[Place]] | None:
    index = _dong_index(catalog)
    hits = [name for name in index if name in message]
    if not hits:
        return None
    name = max(hits, key=len)
    return name, index[name]


def match_place(message: str, catalog: dict[str, Place]) -> Place | None:
    return _match_place(message, catalog)


def has_named_area(message: str, catalog: dict[str, Place]) -> bool:
    """질문에 지역(이름표)·동·구 이름이 있는지 (장소 이름은 제외)."""
    return _match_area(message) is not None or _match_gu(message) is not None or _match_dong(message, catalog) is not None


def resolve_center(
    message: str,
    location: Location | None,
    selected_place_id: str | None,
    last_places: list[PlaceOut],
    last_center: CenterOut | None,
    catalog: dict[str, Place],
) -> Center | None:
    # ① GPS
    if location is not None:
        return Center(lat=location.lat, lng=location.lng, label="현재 위치", source="gps")

    place = _match_place(message, catalog)
    area = _match_area(message)
    dong = _match_dong(message, catalog)
    gu = _match_gu(message)
    named = place is not None or area is not None or dong is not None or gu is not None

    # ② 지시어 → 방금 추천한 장소 (선택한 장소 우선)
    if not named and last_places and any(d in message for d in DEMONSTRATIVES):
        chosen = next((p for p in last_places if p.id == selected_place_id), None) if selected_place_id else None
        chosen = chosen or last_places[0]
        return Center(lat=chosen.lat, lng=chosen.lng, label=chosen.title, source="place", place_id=chosen.id)

    # ③ 카탈로그 장소명
    if place is not None:
        return Center(lat=place.lat, lng=place.lng, label=place.title, source="place", place_id=place.id)

    # ④ 인기 지역 이름표
    if area is not None:
        lat, lng = AREAS[area]
        return Center(lat=lat, lng=lng, label=area, source="area")

    # ⑤ 주소의 동 이름
    if dong is not None:
        name, places = dong
        return _mean_center(places, name, "area")

    # ⑥ 구 이름
    if gu is not None:
        places = [p for p in catalog.values() if p.gu == gu and has_coords(p)]
        if places:
            return _mean_center(places, gu, "gu")

    # ⑦ 직전 기준점
    if last_center is not None:
        # 구 기준점을 이어받으면 source 도 "gu" 그대로 (구 전체에서 고르고 거리는 null — 프론트 요약 바와 일치)
        source = "gu" if last_center.source == "gu" or last_center.label in SEOUL_GU else "history"
        return Center(lat=last_center.lat, lng=last_center.lng, label=last_center.label, source=source)

    # ⑧ 없음
    return None
