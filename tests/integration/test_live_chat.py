"""Q2 Step 1: 실서비스 채팅 통합 테스트 (계획서 Q2 기준).

실제 OpenSearch(seoul-tour-v2)·Ollama·MySQL(chat_message). `test-qa-` 세션만 쓰고 끝나면 지운다.
"""
import uuid

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    sessions = []
    yield TestClient(app), app.state.deps, sessions
    for sid in sessions:
        app.state.deps.history.delete_session(sid)


def ask(live, message, **extra):
    client, _, sessions = live
    sid = f"test-qa-{uuid.uuid4().hex[:12]}"
    sessions.append(sid)
    r = client.post("/api/chat", json={"session_id": sid, "message": message, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_gwanghwamun_food(live):
    body = ask(live, "광화문 근처 맛집 추천해줘")
    places = body["places"]
    assert 3 <= len(places) <= 5
    assert all(p["kind"] == "food" for p in places)
    assert all(p["id"] in live[1].catalog for p in places)
    # 반경 1500m 안이 3곳 이상이면 모두 안쪽, 아니면 채우기/대체 규칙(B5)으로 3곳
    within = [p for p in places if p["distance_m"] <= 1500]
    assert len(within) == len(places) or len(places) == 3


def test_seongsu_cafe_area(live):
    body = ask(live, "성수 카페")
    assert body["center"]["source"] == "area"
    assert body["center"]["label"] == "성수"
    assert body["places"] and all(p["category"] == "카페/전통찻집" for p in body["places"])


def test_thanks_no_places(live):
    body = ask(live, "고마워!")
    assert body["places"] == []
    assert body["center"] is None
