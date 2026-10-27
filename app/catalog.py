"""장소 카탈로그: 원본 seoul_tour.json + 전화번호 보강 파일을 메모리에 올린다.

추천 장소 목록은 항상 이 카탈로그에서 만든다(LLM이 장소를 지어내지 않도록).
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

FOOD_TYPE = "39"
EVENT_TYPE = "15"
TOUR_TYPES = ("12", "14", "28", "38")
CAFE_CAT3 = "A05020900"

# 음식점 세부 분류 (cat3)
FOOD_CAT3_MAP = {
    "A05020100": "한식",
    "A05020200": "양식",
    "A05020300": "일식",
    "A05020400": "중식",
    "A05020700": "이색음식점",
    CAFE_CAT3: "카페/전통찻집",
}

# 기존 vectorize.py 의 cat2_map + 데이터에 실제로 있는 쇼핑(A0401)
CAT2_MAP = {
    "A0101": "자연관광지", "A0201": "역사관광지",
    "A0202": "휴양관광지", "A0203": "체험관광지",
    "A0204": "산업관광지", "A0205": "건축/조형물",
    "A0206": "문화시설", "A0207": "축제",
    "A0208": "공연/행사", "A0301": "레포츠소개",
    "A0302": "육상레포츠", "A0303": "수상레포츠",
    "A0304": "항공레포츠", "A0305": "복합레포츠",
    "A0401": "쇼핑",
}


# 관광공사 신분류(lclsSystm1~3). 2026-10 서울 목록은 절반 넘게 cat1~3 이 비고 신분류만 있다.
# cat3 가 없으면 신분류를 기존 코드로 바꿔서 분류명·카페 판별·OpenSearch cat3 필터가 그대로 동작하게 한다.
# (cat3·신분류가 둘 다 있는 장소의 실제 대응을 보고 정함 — scripts/analyze_list.py, data/raw/lcls_codes.json)
_KOREAN, _WESTERN, _JAPANESE, _CHINESE, _ETHNIC = "A05020100", "A05020200", "A05020300", "A05020400", "A05020700"
LCLS_FOOD_CAT3 = {  # 긴 접두어부터 맞춤
    "FD030100": CAFE_CAT3,  # 제과(베이커리 카페)
    "FD030200": _WESTERN, "FD030300": _WESTERN,  # 피자·햄버거·샌드위치, 치킨
    "FD03": _KOREAN,  # 김밥·분식 등 간이음식
    "FD01": _KOREAN, "FD020100": _CHINESE, "FD020200": _JAPANESE, "FD020300": _WESTERN,
    "FD020400": _ETHNIC, "FD020500": _ETHNIC, "FD05": CAFE_CAT3,
}
LCLS_CAT2 = {  # 긴 접두어부터 맞춤
    "VE040300": "A0101",  # 둘레길 → 자연관광지 (산책)
    "NA": "A0101",
    "HS01": "A0201", "HS03": "A0201", "HS04": "A0201", "HS02": "A0205",
    "VE01": "A0205",
    "VE02": "A0202", "VE03": "A0202", "VE05": "A0202", "EX05": "A0202",
    "VE04": "A0203", "EX01": "A0203", "EX02": "A0203", "EX04": "A0203", "EX07": "A0203",
    "EX06": "A0204",
    "VE06": "A0206", "VE07": "A0206", "VE09": "A0206", "VE12": "A0206",
    "EV01": "A0207", "EV02": "A0208", "EV03": "A0208",
    "LS01": "A0302", "AC05": "A0302", "VE10": "A0302", "LS02": "A0303", "LS03": "A0304", "LS04": "A0305",
    "SH": "A0401",
}
_CULTURE_TYPE = "14"


def _by_prefix(table: dict[str, str], code: str) -> str:
    for prefix in sorted(table, key=len, reverse=True):
        if code.startswith(prefix):
            return table[prefix]
    return ""


def effective_codes(item: dict) -> tuple[str, str]:
    """(cat2, cat3). cat3 가 있으면 원래 값, 없으면 신분류에서 바꾼 값."""
    cat2, cat3 = item.get("cat2", "") or "", item.get("cat3", "") or ""
    if cat3:
        return cat2, cat3
    code = item.get("lclsSystm3", "") or item.get("lclsSystm2", "") or ""
    if str(item.get("contenttypeid")) == FOOD_TYPE:
        return "A0502", _by_prefix(LCLS_FOOD_CAT3, code)
    if str(item.get("contenttypeid")) == _CULTURE_TYPE:
        return "A0206", ""
    return _by_prefix(LCLS_CAT2, code), ""


@dataclass(frozen=True)
class Place:
    id: str
    title: str
    content_type: str
    kind: str  # "food" | "tour" | "event"
    category: str
    cat3: str
    addr: str
    tel: str
    lat: float
    lng: float
    image: str
    gu: str
    # 관광공사 상세 정보 (scripts/enrich_detail.py): parking, hours, rest_day, menu, fee, reservation, pet, stroller,
    # contact, period, place, season, discount, age, packing 중 있는 것만
    detail: dict = field(default_factory=dict, compare=False, hash=False)


def category_name(item: dict) -> str:
    cat2, cat3 = effective_codes(item)
    if item.get("contenttypeid") == FOOD_TYPE:
        name = FOOD_CAT3_MAP.get(cat3)
        if name:
            return name
    return CAT2_MAP.get(cat2, "기타")


def kind_of(content_type: str) -> str:
    if content_type == FOOD_TYPE:
        return "food"
    if content_type == EVENT_TYPE:
        return "event"
    return "tour"


# 서울 주변 범위. 원본에는 좌표가 0(1곳)이거나 (19.69, 117.99)로 잘못 들어간 장소(6곳)가 있다.
SEOUL_BOUNDS = (37.3, 37.8, 126.6, 127.3)  # min_lat, max_lat, min_lng, max_lng


def has_coords(p: Place) -> bool:
    min_lat, max_lat, min_lng, max_lng = SEOUL_BOUNDS
    return bool(p.lat) and bool(p.lng) and min_lat <= p.lat <= max_lat and min_lng <= p.lng <= max_lng


def _gu_of(addr: str) -> str:
    for token in addr.split()[1:3]:
        if token.endswith("구"):
            return token
    return ""


def _float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def place_from_item(item: dict, tel: str = "", detail: dict | None = None) -> Place:
    addr = f"{item.get('addr1', '')} {item.get('addr2', '')}".strip()
    content_type = str(item.get("contenttypeid", ""))
    return Place(
        id=str(item["contentid"]),
        title=item.get("title", "").strip(),
        content_type=content_type,
        kind=kind_of(content_type),
        category=category_name(item),
        cat3=effective_codes(item)[1],
        addr=addr,
        tel=tel or item.get("tel", "") or "",
        lat=_float(item.get("mapy")),
        lng=_float(item.get("mapx")),
        image=item.get("firstimage", "") or "",
        gu=_gu_of(item.get("addr1", "")),
        detail=dict(detail or {}),
    )


def load_raw_items(raw_path="data/seoul_tour.json") -> list[dict]:
    with open(raw_path, encoding="utf-8") as f:
        return json.load(f)["response"]["body"]["items"]["item"]


def load_enriched(enriched_path="data/seoul_tour_enriched.json") -> dict:
    path = Path(enriched_path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_catalog(raw_path="data/seoul_tour.json", enriched_path="data/seoul_tour_enriched.json") -> dict[str, Place]:
    enriched = load_enriched(enriched_path)
    catalog: dict[str, Place] = {}
    for item in load_raw_items(raw_path):
        extra = enriched.get(str(item["contentid"]), {})
        place = place_from_item(item, tel=extra.get("tel", ""), detail=extra.get("detail"))
        catalog[place.id] = place
    return catalog
