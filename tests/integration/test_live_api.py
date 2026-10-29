"""Q1 통합: 실제 OpenSearch(seoul-tour-v3)·Ollama(gemma4:e4b)·MySQL(chat_message)에 붙는 API 테스트.

실행: pytest -m integration -v  (worktree 루트에 .env 필요)
대화 기록은 `test-qa-` 접두 세션만 쓰고 끝나면 지운다. 다른 인덱스·테이블은 건드리지 않는다.
"""
import re
import uuid

import pytest

from app.catalog import SEOUL_BOUNDS
from app.schemas import PlaceOut

pytestmark = pytest.mark.integration

PLACE_KEYS = set(PlaceOut.model_fields)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


@pytest.fixture(scope="module")
def live():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()  # 실제 의존성
    deps = app.state.deps
    sessions = []
    yield TestClient(app), deps, sessions
    for sid in sessions:
        deps.history.delete_session(sid)


def new_sid(sessions):
    sid = f"test-qa-{uuid.uuid4().hex[:12]}"
    sessions.append(sid)
    return sid


def post(client, sid, message, **extra):
    r = client.post("/api/chat", json={"session_id": sid, "message": message, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def check_places(body, catalog):
    min_lat, max_lat, min_lng, max_lng = SEOUL_BOUNDS
    for p in body["places"]:
        assert set(p) == PLACE_KEYS
        assert p["id"] in catalog and catalog[p["id"]].title == p["title"]
        assert p["kind"] in {"food", "tour"}
        assert min_lat <= p["lat"] <= max_lat and min_lng <= p["lng"] <= max_lng, p


def test_live_health(live):
    client, _, _ = live
    assert client.get("/api/health").json() == {"opensearch": True, "ollama": True, "mysql": True}


def test_live_food_near_gwanghwamun_then_cafe(live):
    client, deps, sessions = live
    sid = new_sid(sessions)
    first = post(client, sid, "광화문 근처 맛집 추천해줘")
    check_places(first, deps.catalog)
    assert first["center"]["label"] == "광화문"
    assert 3 <= len(first["places"]) <= 5
    assert all(p["kind"] == "food" for p in first["places"])
    assert first["answer"].strip()

    chosen = first["places"][-1]
    second = post(client, sid, "거기 근처 카페 있어?", selected_place_id=chosen["id"])
    check_places(second, deps.catalog)
    assert second["center"]["label"] == chosen["title"]
    assert second["places"] and all(p["category"] == "카페/전통찻집" for p in second["places"])

    third = post(client, sid, "고마워!")
    assert third["places"] == [] and third["center"] is None

    msgs = client.get(f"/api/history/{sid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"] * 3
    assert all(ISO.match(m["created_at"]) for m in msgs)
    # 기록은 MySQL JSON을 거쳐 좌표 마지막 자리가 달라질 수 있어 좌표만 approx 로 비교
    assert_same_places(msgs[1]["places"], first["places"])
    assert_same_center(msgs[1]["center"], first["center"])
    assert_same_places(msgs[3]["places"], second["places"])


def assert_same_places(a, b):
    assert [p["id"] for p in a] == [p["id"] for p in b]
    for x, y in zip(a, b):
        assert {k: v for k, v in x.items() if k not in ("lat", "lng")} == {k: v for k, v in y.items() if k not in ("lat", "lng")}
        assert x["lat"] == pytest.approx(y["lat"]) and x["lng"] == pytest.approx(y["lng"])


def assert_same_center(a, b):
    assert (a is None) == (b is None)
    if a:
        assert a["label"] == b["label"] and a["source"] == b["source"]
        assert a["lat"] == pytest.approx(b["lat"]) and a["lng"] == pytest.approx(b["lng"])


def test_live_demonstrative_first_message(live):
    client, deps, sessions = live
    body = post(client, new_sid(sessions), "거기 근처 카페 있어?")
    check_places(body, deps.catalog)


def test_live_area_and_gu(live):
    client, deps, sessions = live
    seongsu = post(client, new_sid(sessions), "성수 카페")
    assert seongsu["center"]["source"] == "area"
    check_places(seongsu, deps.catalog)
    assert all(isinstance(p["distance_m"], int) and isinstance(p["walk_min"], int) for p in seongsu["places"])
    jongno = post(client, new_sid(sessions), "종로 관광지")
    assert jongno["center"]["source"] == "gu" and jongno["center"]["label"] == "종로구"
    assert jongno["places"] and all(p["kind"] == "tour" for p in jongno["places"])
    check_places(jongno, deps.catalog)
    # QA-8: 구 기준점이면 거리·도보 null
    assert all(p["distance_m"] is None and p["walk_min"] is None for p in jongno["places"])


def test_live_gps_and_no_location(live):
    client, deps, sessions = live
    gps = post(client, new_sid(sessions), "내 주변 맛집", location={"lat": 37.5759, "lng": 126.9769})
    assert gps["center"]["source"] == "gps" and gps["center"]["label"] == "현재 위치"
    assert gps["places"] and all(p["kind"] == "food" for p in gps["places"])
    check_places(gps, deps.catalog)
    none = post(client, new_sid(sessions), "내 주변 맛집", location=None)
    assert none["center"] is None
    check_places(none, deps.catalog)


def test_live_bad_coord_places_never_returned(live):
    """실데이터의 좌표 0(도심속 바다축제)·서울 밖(계남근린공원 등 6곳)은 places에 없다."""
    client, deps, sessions = live
    for msg in ["이번 주 축제 알려줘", "구로구 관광지", "강서구 공원", "관악구 운동장", "서초구 운동장", "강남구 관광지"]:
        body = post(client, new_sid(sessions), msg)
        check_places(body, deps.catalog)


def test_live_422(live):
    client, _, _ = live
    assert client.post("/api/chat", json={"message": " "}).status_code == 422
    assert client.post("/api/chat", json={"message": "가" * 501}).status_code == 422


def test_live_long_session_id_rejected(live):
    """QA-1(850364d): chat_message.session_id 는 VARCHAR(64) → 65자 이상은 422, 64자는 기록이 남는다."""
    client, _, sessions = live
    assert client.post("/api/chat", json={"session_id": "x" * 65, "message": "고마워!"}).status_code == 422
    sid = "test-qa-" + "x" * 56
    assert len(sid) == 64
    sessions.append(sid)
    post(client, sid, "고마워!")
    assert len(client.get(f"/api/history/{sid}").json()["messages"]) == 2
