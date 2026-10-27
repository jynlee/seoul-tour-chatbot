"""실서비스 멀티턴 통합 테스트 (OpenSearch·Ollama·MySQL 켜진 상태). pytest -m integration"""
import uuid

import pytest

pytestmark = pytest.mark.integration

CAFE = "A05020900"


@pytest.fixture(scope="module")
def live():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    client = TestClient(app)
    sessions = []
    yield client, app.state.deps, sessions
    for sid in sessions:
        app.state.deps.history.delete_session(sid)


def test_live_multiturn_myeongdong(live):
    client, deps, sessions = live
    sid = f"test-live-mt-{uuid.uuid4().hex[:12]}"
    sessions.append(sid)

    def say(message, **extra):
        r = client.post("/api/chat", json={"session_id": sid, "message": message, **extra}, timeout=120)
        assert r.status_code == 200, r.text
        return r.json()

    r1 = say("명동 맛집 추천해줘")
    assert r1["center"]["label"] == "명동" and r1["places"]
    assert all(p["kind"] == "food" for p in r1["places"])

    r2 = say("카페는?")
    assert r2["center"]["label"] == "명동"
    assert r2["places"] and all(deps.catalog[p["id"]].cat3 == CAFE for p in r2["places"])

    r3 = say("다른 데 더 추천해줘")
    if r3["places"]:
        assert r3["center"]["label"] == "명동"
        assert all(deps.catalog[p["id"]].cat3 == CAFE for p in r3["places"])
        assert not {p["id"] for p in r3["places"]} & {p["id"] for p in r2["places"]}
        target = r3["places"][1] if len(r3["places"]) > 1 else r3["places"][0]
        r4 = say("두 번째 거기 어디야?" if len(r3["places"]) > 1 else "첫 번째 거기 어디야?")
        assert r4["places"] == [] and r4["center"] is None
        assert r4["answer"]
        # 핀 유지: 마지막 추천은 r3 그대로
        assert [p.id for p in deps.history.last_assistant(sid).places] == [p["id"] for p in r3["places"]]
        assert target["id"] in deps.catalog

    # 모든 장소는 카탈로그에 있어야 함 (지어낸 장소 없음)
    for r in (r1, r2, r3):
        assert all(p["id"] in deps.catalog for p in r["places"])


def test_live_parenthesized_title_and_clarify(live):
    """사용자 재현: '대원군별장(석파정)'을 '석파정'·'대원군별장'으로 부르기 + 되묻기 뒤 이름만 답하기."""
    client, deps, sessions = live
    sid = f"test-live-sp-{uuid.uuid4().hex[:12]}"
    sessions.append(sid)

    def say(message):
        r = client.post("/api/chat", json={"session_id": sid, "message": message}, timeout=120)
        assert r.status_code == 200, r.text
        return r.json()

    assert say("종로 관광지 추천해줘")["places"]
    r2 = say("석파정 무료 입장이야?")
    assert r2["answer"].startswith("대원군별장(석파정) — 요금 정보는 없어요") and "02-395-0100" in r2["answer"]
    assert r2["places"] == [] and r2["center"] is None


    # 새 세션: 장소 없이 물음 → 되묻기 → 이름만 답하면 앞 질문(요금)에 답함
    sid = f"test-live-sp-{uuid.uuid4().hex[:12]}"
    sessions.append(sid)
    assert say("종로 관광지 추천해줘")["places"]
    from app.llm import CLARIFY_ANSWER
    assert say("무료 입장이야?")["answer"] == CLARIFY_ANSWER
    r3 = say("대원군별장")
    assert r3["answer"].startswith("대원군별장(석파정) — 요금 정보는 없어요") and "02-395-0100" in r3["answer"]
    assert r3["places"] == [] and r3["center"] is None


def test_live_qa9_gu_without_match(live):
    """QA-9: 강서구엔 카페가 없음 → 다른 구 카페, 거리·도보 null, 답에서 다른 구라는 걸 알 수 있음."""
    client, deps, sessions = live
    sid = f"test-live-qa9-{uuid.uuid4().hex[:12]}"
    sessions.append(sid)
    r = client.post("/api/chat", json={"session_id": sid, "message": "강서구 카페 추천해줘"}, timeout=120).json()
    assert (r["center"]["source"], r["center"]["label"]) == ("gu", "강서구")
    assert r["places"] and all(p["distance_m"] is None and p["walk_min"] is None for p in r["places"])
    others = {deps.catalog[p["id"]].gu for p in r["places"]}
    assert "강서구" not in others
    assert "다른 구" in r["answer"] or any(g in r["answer"] for g in others), r["answer"]
