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
    if item.get("contenttypeid") == FOOD_TYPE:
        name = FOOD_CAT3_MAP.get(item.get("cat3", ""))
        if name:
            return name
    return CAT2_MAP.get(item.get("cat2", ""), "기타")


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
        cat3=item.get("cat3", ""),
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
