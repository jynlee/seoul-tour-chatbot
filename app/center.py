""""근처"의 기준점 결정 (spec §5.2).

우선순위: ① GPS ② 지시어("거기 근처")→방금 추천한 장소 ③ 카탈로그 장소명 ④ 인기 지역 이름표
⑤ 주소의 동 이름 ⑥ 구 이름(“종로”처럼 '구'를 뗀 이름도) ⑦ 직전 기준점 ⑧ 없음.
"""
import re
from dataclasses import dataclass

from app.catalog import Place, has_coords
from app.geo import AREAS, SEOUL_GU, haversine_m
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

# 괄호가 든 제목('대원군별장(석파정)', '길상사(서울)')은 사람들이 괄호를 뺀 이름이나 괄호 안 이름으로 부른다.
# 괄호 안 말 중 이름이 아닌 것: 지역 표시('서울')·설명('실내'·'일본군 위안부')·지점('강남코엑스점')·옛 이름 설명('구 ○○')·한 글자
_PAREN = re.compile(r"\s*\(([^)]*)\)\s*")
_NOT_NAMES = {"서울", "실내", "실외", "일본군 위안부"}
_BRACKET = re.compile(r"\[[^\]]*\]")
_AND_HEAD = re.compile(r"^([^\s\[\]]+?)\s?(?:과|와)\s")


@dataclass
class Center:
    lat: float
    lng: float
    label: str
    source: str  # gps | place | area | gu | history
    place_id: str | None = None  # 기준점이 장소일 때(이어받은 history 포함) 그 장소 id (추천 결과에서 자기 자신은 뺌)

    def to_out(self) -> CenterOut:
        return CenterOut(lat=self.lat, lng=self.lng, label=self.label, source=self.source)


def _gu_aliases() -> list[tuple[str, str]]:
    """(질문에서 찾을 이름, 구 이름). '종로'처럼 구를 뗀 이름은 두 글자 이상일 때만."""
    aliases = [(gu, gu) for gu in SEOUL_GU]
    aliases += [(gu[:-1], gu) for gu in SEOUL_GU if len(gu[:-1]) >= 2]
    return sorted(aliases, key=lambda a: -len(a[0]))


GU_ALIASES = _gu_aliases()

# 지역 이름과 같은 제목의 장소('한강'·'명동'·'홍대'·'강남')는 사람들이 거의 늘 지역을 뜻해서 말한다 → 이름 찾기에서 뺀다.
AREA_LIKE_TITLES = frozenset(AREAS) | {alias for alias, _gu in GU_ALIASES} | {"한강", "서울"}


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


def title_aliases(title: str) -> list[str]:
    """장소를 부르는 이름 후보: 원래 제목 + 괄호 뺀 이름 + (이름다운) 괄호 안 이름 + 문화재식 제목에서 뗀 이름."""
    names = _paren_aliases(title)
    return names + [n for n in _heritage_aliases(title) if n not in names]


def _paren_aliases(title: str) -> list[str]:
    names = [title]
    base = _without_parens(title)
    if base != title and len(base.replace(" ", "")) >= 2:
        names.append(base)
    for inner in _PAREN.findall(title):
        inner = " ".join(inner.split())
        if (len(inner.replace(" ", "")) < 2 or inner in _NOT_NAMES or inner.startswith("구 ")
                or inner.endswith("점") or inner in names):
            continue
        names.append(inner)
    return names


def _heritage_aliases(title: str) -> list[str]:
    """문화재식 제목('서울 운현궁'·'창덕궁과 후원 [유네스코 세계유산]'·'[서울둘레길 3코스] 불암산코스'):
    대괄호 설명을 뗀 이름 → 앞의 '서울 '을 뗀 이름 → 첫 낱말이 '○○과/와'면 그 앞 이름 (QA-10)."""
    plain = " ".join(_BRACKET.sub(" ", _without_parens(title)).split())
    no_seoul = plain[len("서울 "):] if plain.startswith("서울 ") else plain
    head = _AND_HEAD.match(no_seoul)
    names: list[str] = []
    for name in (plain, no_seoul, head.group(1) if head else ""):
        if len(name.replace(" ", "")) >= 2 and name != title and name not in names:
            names.append(name)
    return names


def _without_parens(title: str) -> str:
    return " ".join(_PAREN.sub(" ", title).split())


def _alias_used(alias: str, text: str) -> bool:
    """이름이 질문에 장소로 쓰였는지 (영문은 대소문자 무시). 2글자 이하 이름은 장소로 쓰인 말이 따라올 때만."""
    alias, text = alias.lower(), text.lower()
    if alias not in text:
        return False
    return len(alias.replace(" ", "")) > SHORT_TITLE_LEN or _short_title_used_as_place(alias, text)


def matched_alias(title: str, text: str, loose_title: bool = False) -> str | None:
    """질문에 들어 있는 이 장소의 이름 중 가장 긴 것. loose_title: 원래 제목은 2글자 규칙 없이 부분 문자열로."""
    hits = [a for i, a in enumerate(title_aliases(title))
            if (loose_title and i == 0 and a in text) or _alias_used(a, text)]
    return max(hits, key=len) if hits else None


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
    """장소 이름(괄호 뺀 이름·괄호 안 이름 포함)이 질문에 있으면: 정확히 같은 이름 > 가장 긴 이름 > 제목·괄호 별칭 > 덧붙은 말이 적은 제목 > 가장 짧은 id."""
    text = message.strip()
    # 지역·구 이름과 같거나 그 안에 들어 있는 이름(예: '강남'=강남구, '강남역' 속 '강남')은 장소로 보지 않는다.
    # → 구/지역 이름이 같은 이름의 장소보다 우선.
    bigger_names = [n for n in AREAS if n in text]
    alias = _match_gu_alias(text)
    if alias:
        bigger_names.append(alias)
    candidates = []
    for p in catalog.values():
        if not p.title or not has_coords(p):
            continue
        hits = [a for a in title_aliases(p.title)
                if a not in AREA_LIKE_TITLES and _alias_used(a, text) and not any(a in n for n in bigger_names)]
        if not hits:
            continue
        exact = any(a.lower() == text.lower() for a in hits)
        best = max(hits, key=len)
        # 같은 이름이면 제목·괄호 별칭인 장소 먼저, 문화재식 제목에서 뗀 이름끼리는 덧붙은 말('서울 '·'[K드라마 촬영지]')이
        # 적은 제목 = 대표 장소(본체) 먼저
        derived = best not in _paren_aliases(p.title)
        candidates.append((not exact, -len(best), derived, len(p.title) - len(best) if derived else 0,
                           len(p.id), p.id, p))
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[:6])[6]


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
        # 장소 기준점을 이어받으면 그 장소 id도 (추천에서 자기 자신·세부 장소를 빼게)
        same = next((p.id for p in catalog.values() if p.title == last_center.label and has_coords(p)
                     and haversine_m(p.lat, p.lng, last_center.lat, last_center.lng) <= 10), None)
        return Center(lat=last_center.lat, lng=last_center.lng, label=last_center.label, source=source, place_id=same)

    # ⑧ 없음
    return None
