from app.center import resolve_center
from app.schemas import CenterOut, Location, PlaceOut


def _out(place):
    return PlaceOut(id=place.id, title=place.title, kind="food" if place.kind == "food" else "tour",
                    category=place.category, addr=place.addr, tel=place.tel, lat=place.lat, lng=place.lng,
                    image=place.image)


def _resolve(catalog, message, location=None, selected=None, last_places=(), last_center=None):
    return resolve_center(message, location, selected, list(last_places), last_center, catalog)


def test_gps_wins(small_catalog):
    c = _resolve(small_catalog, "광화문 근처 맛집", location=Location(lat=37.5, lng=127.0))
    assert c.source == "gps"
    assert c.label == "현재 위치"
    assert (c.lat, c.lng) == (37.5, 127.0)


def test_demonstrative_uses_selected(small_catalog):
    last = [_out(small_catalog["2543919"]), _out(small_catalog["398373"])]
    c = _resolve(small_catalog, "거기 근처 카페 있어?", selected="398373", last_places=last)
    assert c.label == "개성만두 궁"
    assert c.source == "place"


def test_demonstrative_uses_first_when_none_selected(small_catalog):
    last = [_out(small_catalog["2543919"]), _out(small_catalog["398373"])]
    c = _resolve(small_catalog, "거기 근처 카페 있어?", last_places=last)
    assert c.label == "광화문 세종클럽"


def test_demonstrative_selected_not_in_last_uses_first(small_catalog):
    last = [_out(small_catalog["2543919"])]
    c = _resolve(small_catalog, "그 근처 관광지", selected="775394", last_places=last)
    assert c.label == "광화문 세종클럽"


def test_demonstrative_without_history_falls_through(small_catalog):
    assert _resolve(small_catalog, "거기 근처 카페 있어?") is None


def test_demonstrative_ignored_when_place_named(small_catalog):
    last = [_out(small_catalog["398373"])]
    c = _resolve(small_catalog, "거기 말고 광화문광장 근처", last_places=last)
    assert c.label == "광화문광장"


def test_place_title_longest_match(small_catalog):
    c = _resolve(small_catalog, "광화문광장 근처 맛집")
    assert c.label == "광화문광장"
    assert c.source == "place"


def test_place_title_exact(small_catalog):
    c = _resolve(small_catalog, "광화문")
    assert c.label == "광화문"


def test_place_without_coords_skipped(small_catalog):
    assert _resolve(small_catalog, "도심속 바다축제 어때") is None


def test_area_name(small_catalog):
    c = _resolve(small_catalog, "성수 카페")
    assert (c.lat, c.lng) == (37.5446, 127.0559)
    assert c.source == "area"
    assert c.label == "성수"


def test_dong_name_from_addr(small_catalog):
    c = _resolve(small_catalog, "관훈동 맛집")
    assert c.source == "area"
    assert c.label == "관훈동"
    assert abs(c.lat - 37.5743229) < 1e-6


def test_gu_name(small_catalog):
    c = _resolve(small_catalog, "종로구 관광지")
    assert c.source == "gu"
    assert c.label == "종로구"


def test_gu_stem(small_catalog):
    c = _resolve(small_catalog, "종로 관광지")
    assert c.source == "gu"
    assert c.label == "종로구"


def test_history_fallback(small_catalog):
    last_center = CenterOut(lat=37.57, lng=126.97, label="광화문", source="place")
    c = _resolve(small_catalog, "맛집 더 알려줘", last_center=last_center)
    assert c.source == "history"
    assert c.label == "광화문"


def test_none(small_catalog):
    assert _resolve(small_catalog, "맛집 추천해줘") is None


# ---- 2글자 장소명: 일반 단어로 쓰이면 기준점이 아님 ----

def _with_short_titles(small_catalog):
    import dataclasses

    catalog = dict(small_catalog)
    base = small_catalog["2622715"]  # 감꽃당(카페) 좌표를 빌려 씀
    for pid, title in (("2901568", "기후"), ("2870486", "길목")):
        catalog[pid] = dataclasses.replace(base, id=pid, title=title)
    return catalog


def test_short_title_as_whole_message_or_place_usage(small_catalog):
    catalog = _with_short_titles(small_catalog)
    assert _resolve(catalog, "기후").label == "기후"
    assert _resolve(catalog, "기후?").label == "기후"
    assert _resolve(catalog, "기후 맛집").label == "기후"
    assert _resolve(catalog, "기후 근처 카페 있어?").label == "기후"
    assert _resolve(catalog, "길목에서 가까운 카페").label == "길목"
    assert _resolve(catalog, "구펠 주변 관광지").label == "구펠"


def test_short_title_as_common_word_is_ignored(small_catalog):
    catalog = _with_short_titles(small_catalog)
    assert _resolve(catalog, "기후 변화 걱정 없는 실내 관광지 추천해줘") is None
    assert _resolve(catalog, "요즘 서울 기후 어때?") is None
    assert _resolve(catalog, "골목길목 분위기 좋은 카페") is None
    assert _resolve(catalog, "길목마다 맛집이 있는 곳") is None
