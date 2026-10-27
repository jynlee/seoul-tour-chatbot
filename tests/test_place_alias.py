"""괄호가 든 장소 이름('대원군별장(석파정)', '길상사(서울)')을 사람들이 부르는 이름으로 찾기. 실제 카탈로그."""
import pytest

from app.catalog import load_catalog
from app.center import match_place, resolve_center, title_aliases
from app.dialog import resolve_reference
from app.schemas import PlaceOut
from tests.conftest import CATALOG_574


@pytest.fixture(scope="module")
def catalog(tmp_path_factory):
    return load_catalog(CATALOG_574, tmp_path_factory.mktemp("e") / "none.json")


def _out(p):
    return PlaceOut(id=p.id, title=p.title, kind="food" if p.kind == "food" else "tour", category=p.category,
                    addr=p.addr, tel=p.tel, lat=p.lat, lng=p.lng, image=p.image)


def _title(place):
    return place.title if place else None


def test_title_aliases():
    assert title_aliases("대원군별장(석파정)") == ["대원군별장(석파정)", "대원군별장", "석파정"]
    assert title_aliases("길상사(서울)") == ["길상사(서울)", "길상사"]  # '서울'은 이름이 아님
    assert title_aliases("관훈동 민씨 가옥 (구 부마도위박영효가옥)") == ["관훈동 민씨 가옥 (구 부마도위박영효가옥)",
                                                                  "관훈동 민씨 가옥"]  # 옛 이름 설명 제외
    assert title_aliases("목동아이스링크(실내)") == ["목동아이스링크(실내)", "목동아이스링크"]
    assert title_aliases("양천 락(樂) 페스티벌") == ["양천 락(樂) 페스티벌", "양천 락 페스티벌"]  # 한 글자 제외
    assert title_aliases("세븐럭카지노(강남코엑스점)") == ["세븐럭카지노(강남코엑스점)", "세븐럭카지노"]  # 지점 설명 제외
    assert title_aliases("기억의 터(일본군 위안부)") == ["기억의 터(일본군 위안부)", "기억의 터"]
    assert title_aliases("광화문") == ["광화문"]


@pytest.mark.parametrize("message,title", [
    ("석파정 무료 입장이야?", "대원군별장(석파정)"),
    ("대원군별장", "대원군별장(석파정)"),
    ("대원군별장 주차 돼?", "대원군별장(석파정)"),
    ("길상사 가는 길 알려줘", "길상사(서울)"),
    ("간송미술관 근처 맛집", "간송미술관(서울 보화각)"),
    ("국기원 몇 시에 열어?", "국기원(세계태권도본부)"),
    ("세계태권도본부 어디야?", "국기원(세계태권도본부)"),
    ("라이트룸 서울 근처 카페", "라이트룸 서울(Lightroom Seoul)"),
    ("kspo dome 근처 맛집", "올림픽체조경기장(KSPO DOME)"),
    ("남산공원 근처 카페", "남산공원(서울)"),
    ("관훈동 민씨 가옥 주차 돼?", "관훈동 민씨 가옥 (구 부마도위박영효가옥)"),
])
def test_match_place_by_alias(catalog, message, title):
    assert _title(match_place(message, catalog)) == title


@pytest.mark.parametrize("message", [
    "남산 맛집 추천해줘",          # 지역 '남산' 우선 (남산공원(서울)으로 오인 X)
    "서울 관광지 추천해줘",        # 괄호 속 '서울'은 이름 아님
    "공기 좋은 곳 추천해줘",       # '공기(Gongi)' → '공기'는 2글자 규칙
    "실내 관광지 추천해줘",        # '목동아이스링크(실내)'
    "강남 관광지 알려줘",          # 구 우선
])
def test_alias_does_not_steal_common_words(catalog, message):
    assert match_place(message, catalog) is None


def test_namsan_area_still_area(catalog):
    c = resolve_center("남산 맛집 추천해줘", None, None, [], None, catalog)
    assert (c.source, c.label) == ("area", "남산")


def test_reference_in_last_list_by_alias(catalog):
    by_title = {p.title: p for p in catalog.values()}
    last = [_out(by_title["바라캇 서울"]), _out(by_title["대원군별장(석파정)"])]
    for message in ("석파정 무료 입장이야?", "대원군별장"):
        ref = resolve_reference(message, None, last, None, catalog)
        assert ref is not None and ref.place.title == "대원군별장(석파정)", message
        assert ref.kind == "title"
