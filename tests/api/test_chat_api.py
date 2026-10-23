"""Q1: POST /api/chat — 계약·시나리오·Review Focus (가짜 의존성)."""
import re
import uuid

import pytest

from app.catalog import CAFE_CAT3, SEOUL_BOUNDS
from app.intent import CASUAL_RESPONSES
from app.llm import template_answer
from app.main import SEARCH_UNAVAILABLE_DETAIL
from app.schemas import PlaceOut
from tests.api.conftest import BAD_COORD_ID, ZERO_COORD_ID, chat
from tests.conftest import FakeSearcher

PLACE_KEYS = set(PlaceOut.model_fields)
GWANGHWAMUN_FOOD = "광화문 근처 맛집 추천해줘"


def in_seoul(lat, lng):
    min_lat, max_lat, min_lng, max_lng = SEOUL_BOUNDS
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


def assert_contract(body, catalog):
    assert set(body) == {"session_id", "answer", "center", "places"}
    assert isinstance(body["answer"], str) and body["answer"]
    if body["center"] is not None:
        assert set(body["center"]) == {"lat", "lng", "label", "source"}
        assert body["center"]["source"] in {"gps", "place", "area", "gu", "history"}
    for p in body["places"]:
        assert set(p) == PLACE_KEYS
        assert p["kind"] in {"food", "tour"}
        assert p["id"] in catalog, f"카탈로그에 없는 장소: {p}"
        assert catalog[p["id"]].title == p["title"]
        assert isinstance(p["tel"], str) and isinstance(p["image"], str)
        assert in_seoul(p["lat"], p["lng"]), f"좌표가 서울 밖: {p}"
        if body["center"] is None:
            assert p["distance_m"] is None and p["walk_min"] is None
        else:
            assert isinstance(p["distance_m"], int) and isinstance(p["walk_min"], int)


# ---------------------------------------------------------------- 계약

def test_contract_food_near_gwanghwamun(client, catalog):
    status, body = chat(client, GWANGHWAMUN_FOOD)
    assert status == 200
    assert_contract(body, catalog)
    assert body["center"]["label"] == "광화문"
    assert body["center"]["source"] == "place"
    assert 3 <= len(body["places"]) <= 5
    assert all(p["kind"] == "food" for p in body["places"])
    assert all(p["distance_m"] <= 1500 for p in body["places"])
    dists = [p["distance_m"] for p in body["places"]]
    assert dists == sorted(dists)
    assert body["answer"] == "추천 장소를 골라봤어요."


def test_new_session_is_uuid_and_second_turn_keeps_session(client):
    _, first = chat(client, GWANGHWAMUN_FOOD)
    uuid.UUID(first["session_id"])
    _, second = chat(client, "관광지도 알려줘", session_id=first["session_id"])
    assert second["session_id"] == first["session_id"]
    h = client.get(f"/api/history/{first['session_id']}").json()
    assert len(h["messages"]) == 4


def test_given_session_id_is_echoed(client):
    _, body = chat(client, GWANGHWAMUN_FOOD, session_id="my-session-1")
    assert body["session_id"] == "my-session-1"


def test_two_new_sessions_are_different(client):
    _, a = chat(client, GWANGHWAMUN_FOOD)
    _, b = chat(client, GWANGHWAMUN_FOOD)
    assert a["session_id"] != b["session_id"]


# ---------------------------------------------------------------- 입력 검증 (422)

@pytest.mark.parametrize("payload", [
    {"message": ""},
    {"message": "   "},
    {"message": "\n\t "},
    {"message": "가" * 501},
    {},
    {"message": None},
    {"message": "맛집", "location": {"lat": "abc", "lng": 126.97}},
    {"message": "맛집", "location": {"lat": 37.5}},
])
def test_invalid_request_422(client, payload):
    r = client.post("/api/chat", json=payload)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)  # FastAPI 기본 검증 형식


def test_500_chars_ok_and_strip_before_length_check(client):
    assert client.post("/api/chat", json={"message": "가" * 500}).status_code == 200
    # 앞뒤 공백은 제거한 뒤 길이를 잰다
    assert client.post("/api/chat", json={"message": "  " + "가" * 500 + "  "}).status_code == 200


def test_message_saved_stripped(client):
    _, body = chat(client, "   광화문 근처 맛집   ")
    h = client.get(f"/api/history/{body['session_id']}").json()
    assert h["messages"][0]["message"] == "광화문 근처 맛집"


# ---------------------------------------------------------------- 멀티턴 "거기 근처"

def test_demonstrative_with_selected_place(client, catalog):
    _, first = chat(client, GWANGHWAMUN_FOOD)
    assert "398373" in [p["id"] for p in first["places"]]
    status, res = chat(client, "거기 근처 카페 있어?", session_id=first["session_id"],
                       selected_place_id="398373")
    assert status == 200
    assert_contract(res, catalog)
    assert res["center"]["label"] == "개성만두 궁"
    assert res["center"]["source"] == "place"
    assert res["places"]
    assert all(catalog[p["id"]].cat3 == CAFE_CAT3 for p in res["places"])


def test_demonstrative_without_selection_uses_first_previous_place(client, catalog):
    _, first = chat(client, GWANGHWAMUN_FOOD)
    first_place = first["places"][0]
    _, res = chat(client, "거기 근처 카페 있어?", session_id=first["session_id"])
    assert res["center"]["label"] == first_place["title"]
    assert (res["center"]["lat"], res["center"]["lng"]) == (first_place["lat"], first_place["lng"])
    assert all(catalog[p["id"]].cat3 == CAFE_CAT3 for p in res["places"])


def test_demonstrative_with_unknown_selected_id_falls_back_to_first(client):
    _, first = chat(client, GWANGHWAMUN_FOOD)
    _, res = chat(client, "거기 근처 카페 있어?", session_id=first["session_id"],
                  selected_place_id="없는아이디")
    assert res["center"]["label"] == first["places"][0]["title"]


def test_demonstrative_as_first_message_no_error(client, catalog):
    """Review Focus 3: 직전 추천 없이 "거기 근처" → 지시어 규칙을 건너뛰고 오류 없음."""
    status, res = chat(client, "거기 근처 카페 있어?")
    assert status == 200
    assert_contract(res, catalog)
    assert res["center"] is None
    assert all(catalog[p["id"]].cat3 == CAFE_CAT3 for p in res["places"])


def test_demonstrative_after_only_casual_no_error(client):
    _, first = chat(client, "고마워!")
    status, res = chat(client, "거기 근처 맛집 알려줘", session_id=first["session_id"])
    assert status == 200
    assert res["center"] is None


def test_new_recommendation_replaces_places(client, catalog):
    _, first = chat(client, GWANGHWAMUN_FOOD)
    sid = first["session_id"]
    _, second = chat(client, "종로 관광지", session_id=sid)
    assert second["center"]["source"] == "gu"
    assert second["places"] and all(p["kind"] == "tour" for p in second["places"])
    assert {p["id"] for p in second["places"]}.isdisjoint({p["id"] for p in first["places"]})
    # 이후 "거기 근처"는 새 추천의 첫 장소 기준
    _, third = chat(client, "거기 근처 맛집 알려줘", session_id=sid)
    assert third["center"]["label"] == second["places"][0]["title"]
    # 새로고침 복원용 기록의 마지막 봇 메시지도 새 추천
    h = client.get(f"/api/history/{sid}").json()
    assert h["messages"][3]["places"] == second["places"]


def test_history_center_carried_over(client):
    _, first = chat(client, GWANGHWAMUN_FOOD)
    _, res = chat(client, "관광지도 알려줘", session_id=first["session_id"])
    assert res["center"]["source"] == "history"
    assert res["center"]["label"] == "광화문"


def test_casual_reply(client):
    _, first = chat(client, GWANGHWAMUN_FOOD)
    status, res = chat(client, "고마워!", session_id=first["session_id"])
    assert status == 200
    assert res["places"] == [] and res["center"] is None
    assert res["answer"] in CASUAL_RESPONSES


# ---------------------------------------------------------------- Review Focus 1: LLM 다운

def test_llm_down_returns_template(client, deps, catalog):
    deps.llm.fail = True
    status, body = chat(client, GWANGHWAMUN_FOOD)
    assert status == 200
    assert_contract(body, catalog)
    places = [PlaceOut(**p) for p in body["places"]]
    assert places
    assert body["answer"] == template_answer(places, "광화문")
    assert body["answer"].startswith("광화문 근처 추천 장소를 지도에 표시했어요: ")


def test_llm_down_without_center(client, deps):
    deps.llm.fail = True
    _, body = chat(client, "관광지 추천해줘")
    places = [PlaceOut(**p) for p in body["places"]]
    assert body["center"] is None
    assert body["answer"] == template_answer(places, None)


def test_llm_down_with_fallback_note(client, deps):
    """반경 안에 장소가 없어 가까운 곳으로 대체하면 템플릿 뒤에 안내가 붙는다."""
    deps.llm.fail = True
    _, body = chat(client, "성수 관광지 알려줘")
    assert body["center"]["source"] == "area"
    places = [PlaceOut(**p) for p in body["places"]]
    assert len(places) == 3 and all(p.distance_m > 1500 for p in places)
    base = template_answer(places, "성수")
    assert body["answer"].startswith(base)
    tail = body["answer"][len(base):]
    assert re.fullmatch(rf" \(가장 가까운 곳은 \d+\.\dkm 떨어진 {re.escape(places[0].title)}예요\)", tail)


def test_llm_down_no_places(client, deps):
    deps.llm.fail = True
    _, body = chat(client, "축제 알려줘")
    assert body["places"] == []
    assert body["answer"] == template_answer([], None)


def test_llm_down_does_not_break_history(client, deps):
    deps.llm.fail = True
    _, body = chat(client, GWANGHWAMUN_FOOD)
    h = client.get(f"/api/history/{body['session_id']}").json()
    assert h["messages"][1]["message"] == body["answer"]


# ---------------------------------------------------------------- Review Focus 2: OpenSearch 다운

def test_search_down_503_korean_detail(client, deps):
    deps.searcher.fail = True
    r = client.post("/api/chat", json={"message": GWANGHWAMUN_FOOD})
    assert r.status_code == 503
    assert r.json() == {"detail": "검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."}
    assert SEARCH_UNAVAILABLE_DETAIL == r.json()["detail"]


def test_search_down_casual_still_works(client, deps):
    deps.searcher.fail = True
    status, body = chat(client, "고마워!")
    assert status == 200 and body["places"] == []


def test_search_recovers_after_503(client, deps):
    deps.searcher.fail = True
    assert client.post("/api/chat", json={"message": GWANGHWAMUN_FOOD}).status_code == 503
    deps.searcher.fail = False
    assert client.post("/api/chat", json={"message": GWANGHWAMUN_FOOD}).status_code == 200


# ---------------------------------------------------------------- Review Focus 4: 전화·사진 없는 장소

def test_missing_tel_and_image_are_empty_strings(client, catalog):
    _, body = chat(client, GWANGHWAMUN_FOOD)
    gaesung = next(p for p in body["places"] if p["id"] == "398373")
    assert gaesung["tel"] == "" and gaesung["image"] == ""


def test_tel_present_passes_through(client):
    _, body = chat(client, "가회동성당 근처 관광지")
    church = next(p for p in body["places"] if p["id"] == "2733967")
    assert church["tel"] == "02-763-1570"
    assert church["image"] == ""


# ---------------------------------------------------------------- Review Focus 5: GPS 거부·위치 없음

GPS = {"lat": 37.5759, "lng": 126.9769}


def test_gps_location_used(client, catalog):
    _, body = chat(client, "내 주변 맛집", location=GPS)
    assert_contract(body, catalog)
    assert body["center"] == {"lat": GPS["lat"], "lng": GPS["lng"], "label": "현재 위치", "source": "gps"}
    assert body["places"] and all(p["kind"] == "food" for p in body["places"])


@pytest.mark.parametrize("extra", [{}, {"location": None}])
def test_no_location_request(client, catalog, extra):
    """GPS 거부/미지원 → 프론트는 location: null(또는 생략)으로 보냄 → 오류 없이 처리."""
    status, body = chat(client, "내 주변 맛집", **extra)
    assert status == 200
    assert_contract(body, catalog)
    assert body["center"] is None
    assert all(p["kind"] == "food" for p in body["places"])


def test_gps_then_denied_next_request_not_gps(client):
    _, first = chat(client, "내 주변 맛집", location=GPS)
    _, second = chat(client, "관광지도 알려줘", session_id=first["session_id"], location=None)
    assert second["center"]["source"] == "history"


def test_gps_wins_over_place_name(client):
    _, body = chat(client, "광화문 근처 맛집", location={"lat": 37.5484, "lng": 127.0470})
    assert body["center"]["source"] == "gps"


# ---------------------------------------------------------------- 잘못된 좌표·지어낸 장소

def test_bad_coord_places_never_returned(catalog, deps, client):
    # 검색 점수가 가장 높아도 좌표 0 / 서울 밖 장소는 나오지 않는다
    deps.searcher.scores = {BAD_COORD_ID: 9.0, ZERO_COORD_ID: 9.0}
    for msg in ["맛집 추천해줘", GWANGHWAMUN_FOOD, "종로 맛집", "성수 맛집", "축제 알려줘", "축제랑 맛집"]:
        _, body = chat(client, msg)
        ids = {p["id"] for p in body["places"]}
        assert BAD_COORD_ID not in ids and ZERO_COORD_ID not in ids, msg
        assert_contract(body, catalog)


def test_gu_center_ignores_bad_coords(client):
    _, body = chat(client, "종로 맛집")
    assert body["center"]["source"] == "gu"
    assert in_seoul(body["center"]["lat"], body["center"]["lng"])


def test_bad_coord_place_name_is_not_center(client):
    _, body = chat(client, "도심속 바다축제 근처 맛집")
    assert body["center"] is None or body["center"]["label"] != "도심속 바다축제"


class GhostSearcher(FakeSearcher):
    """카탈로그에 없는 id를 섞어 돌려주는 검색 서버."""

    def knn(self, vector, content_types, cat3, k):
        return [("0000001", 99.0), ("가짜", 98.0)] + super().knn(vector, content_types, cat3, k)


def test_llm_invented_place_not_in_places(client, deps, catalog):
    deps.llm.answer = "광화문 근처에는 '하늘나라 국밥'과 '없는카페'가 최고예요!"
    deps.searcher = GhostSearcher(catalog)
    _, body = chat(client, GWANGHWAMUN_FOOD)
    titles = {p["title"] for p in body["places"]}
    assert "하늘나라 국밥" not in titles and "없는카페" not in titles
    assert all(p["id"] in catalog for p in body["places"])
    assert body["places"]


def test_ghost_ids_from_search_dropped(catalog):
    from fastapi.testclient import TestClient

    from app.chat import Deps
    from app.history import InMemoryHistoryRepo
    from app.main import create_app
    from tests.conftest import FakeEmbedder, FakeLLM

    app = create_app(Deps(catalog=catalog, embedder=FakeEmbedder(), searcher=GhostSearcher(catalog),
                          llm=FakeLLM(), history=InMemoryHistoryRepo()))
    _, body = chat(TestClient(app), "맛집 추천해줘")
    assert body["places"]
    assert all(p["id"] in catalog for p in body["places"])


# ---------------------------------------------------------------- 기록 저장소 장애

class BrokenHistory:
    def save(self, *a, **k):
        raise RuntimeError("MySQL 꺼짐")

    def list(self, sid):
        raise RuntimeError("MySQL 꺼짐")

    def last_assistant(self, sid):
        raise RuntimeError("MySQL 꺼짐")

    def delete_expired(self, days=30):
        raise RuntimeError("MySQL 꺼짐")

    def ping(self):
        raise RuntimeError("MySQL 꺼짐")


def test_chat_works_when_history_down(catalog):
    from fastapi.testclient import TestClient

    from app.chat import Deps
    from app.main import create_app
    from tests.conftest import FakeEmbedder, FakeLLM

    app = create_app(Deps(catalog=catalog, embedder=FakeEmbedder(), searcher=FakeSearcher(catalog),
                          llm=FakeLLM(), history=BrokenHistory()))
    c = TestClient(app)
    status, body = chat(c, GWANGHWAMUN_FOOD)
    assert status == 200 and body["places"]
    assert c.get("/api/health").json()["mysql"] is False
