import uuid

import pytest
from fastapi.testclient import TestClient

from app.chat import ChatService, Deps
from app.history import InMemoryHistoryRepo
from app.intent import CASUAL_RESPONSES
from app.llm import template_answer
from app.main import SEARCH_UNAVAILABLE_DETAIL, create_app
from app.schemas import ChatRequest
from tests.conftest import FakeEmbedder, FakeLLM, FakeSearcher
from tests.conftest import CATALOG_574


@pytest.fixture
def deps(small_catalog):
    return Deps(catalog=small_catalog, embedder=FakeEmbedder(), searcher=FakeSearcher(small_catalog),
                llm=FakeLLM("광화문 근처 맛집을 골라봤어요."), history=InMemoryHistoryRepo())


def test_food_near_gwanghwamun(deps):
    res = ChatService(deps).handle(ChatRequest(message="광화문 근처 맛집 추천해줘"))
    uuid.UUID(res.session_id)
    assert res.center.label == "광화문"
    assert res.center.source == "place"
    assert 1 <= len(res.places) <= 5
    assert all(p.kind == "food" for p in res.places)
    assert all(p.id in deps.catalog for p in res.places)
    assert res.answer == "광화문 근처 맛집을 골라봤어요."
    assert "개성만두 궁" in deps.llm.prompts[0]


def test_demonstrative_cafe_after_selection(deps):
    svc = ChatService(deps)
    first = svc.handle(ChatRequest(message="광화문 근처 맛집 추천해줘"))
    assert "398373" in [p.id for p in first.places]
    res = svc.handle(ChatRequest(session_id=first.session_id, message="거기 근처 카페 있어?",
                                 selected_place_id="398373"))
    assert res.session_id == first.session_id
    assert res.center.label == "개성만두 궁"
    assert res.places and all(deps.catalog[p.id].cat3 == "A05020900" for p in res.places)


def test_llm_down_uses_template(deps):
    deps.llm.fail = True
    res = ChatService(deps).handle(ChatRequest(message="광화문 근처 맛집 추천해줘"))
    assert res.places
    assert res.answer == template_answer(res.places, "광화문")


def test_casual_keeps_last_recommendation(deps):
    svc = ChatService(deps)
    first = svc.handle(ChatRequest(message="광화문 근처 맛집 추천해줘"))
    res = svc.handle(ChatRequest(session_id=first.session_id, message="고마워!"))
    assert res.places == []
    assert res.center is None
    assert res.answer in CASUAL_RESPONSES
    last = deps.history.last_assistant(first.session_id)
    assert [p.id for p in last.places] == [p.id for p in first.places]
    assert len(deps.history.list(first.session_id)) == 4


def test_history_center_carried_over(deps):
    svc = ChatService(deps)
    first = svc.handle(ChatRequest(message="광화문 근처 맛집 추천해줘"))
    res = svc.handle(ChatRequest(session_id=first.session_id, message="관광지도 알려줘"))
    assert res.center.source == "history"
    assert res.center.label == "광화문"


def test_search_unavailable_propagates(deps):
    from app.search import SearchUnavailable

    deps.searcher.fail = True
    with pytest.raises(SearchUnavailable):
        ChatService(deps).handle(ChatRequest(message="광화문 근처 맛집"))


# ---- FastAPI 앱 (기본 동작만, 자세한 API 테스트는 Q1) ----

@pytest.fixture
def client(deps):
    return TestClient(create_app(deps))


def test_api_chat_and_history(client):
    r = client.post("/api/chat", json={"message": "광화문 근처 맛집 추천해줘"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"session_id", "answer", "center", "places"}
    h = client.get(f"/api/history/{body['session_id']}").json()
    assert [m["role"] for m in h["messages"]] == ["user", "assistant"]
    assert h["messages"][1]["places"] == body["places"]
    assert client.get("/api/history/없는세션").json() == {"session_id": "없는세션", "messages": []}


def test_api_503(client, deps):
    deps.searcher.fail = True
    r = client.post("/api/chat", json={"message": "광화문 근처 맛집"})
    assert r.status_code == 503
    assert r.json() == {"detail": SEARCH_UNAVAILABLE_DETAIL}
    assert SEARCH_UNAVAILABLE_DETAIL == "검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."


def test_api_422(client):
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422


def test_api_health(client, deps):
    assert client.get("/api/health").json() == {"opensearch": True, "ollama": True, "mysql": True}
    deps.llm.fail = True
    assert client.get("/api/health").json()["ollama"] is False


# ---- "다른 데 더"가 반경 밖 장소로만 이어질 때 ----

def _far_cafe_catalog(small_catalog):
    import dataclasses

    catalog = dict(small_catalog)
    base = small_catalog["2895236"]  # 구펠(성수) — 인사동에서 약 6km
    for i in range(4):
        pid = f"88800{i}"
        catalog[pid] = dataclasses.replace(base, id=pid, title=f"성수카페{i}", lng=base.lng + 0.001 * (i + 1))
    return catalog


def _far_service(catalog, llm):
    from app.chat import ChatService, Deps
    from app.history import InMemoryHistoryRepo
    from tests.conftest import FakeEmbedder, FakeSearcher

    return ChatService(Deps(catalog=catalog, embedder=FakeEmbedder(), searcher=FakeSearcher(catalog),
                            llm=llm, history=InMemoryHistoryRepo()))


def test_more_only_far_places_says_so(small_catalog):
    from app.schemas import ChatRequest
    from tests.conftest import FakeLLM

    catalog = _far_cafe_catalog(small_catalog)
    llm = FakeLLM("성수 쪽 카페들이에요.")
    svc = _far_service(catalog, llm)
    r1 = svc.handle(ChatRequest(message="인사동 카페 추천해줘"))
    assert r1.places[0].title == "감꽃당"
    r2 = svc.handle(ChatRequest(session_id=r1.session_id, message="다른 데 더 추천해줘"))
    assert r2.places and all(p.distance_m > 1500 for p in r2.places)
    assert r2.answer.startswith("인사동 근처(1.5km 안)에는 더 보여드릴 곳이 없어서 조금 떨어진 곳을 골랐어요.")
    assert r2.answer.endswith("성수 쪽 카페들이에요.")
    assert "1.5km" in llm.prompts[-1] and "근처'라고 하지 말" in llm.prompts[-1]


def test_more_only_far_places_llm_already_says_far(small_catalog):
    # LLM 답이 이미 멀다는 걸 말하면 안내를 또 붙이지 않음 (같은 말 두 번 방지)
    from app.schemas import ChatRequest
    from tests.conftest import FakeLLM

    svc = _far_service(_far_cafe_catalog(small_catalog), FakeLLM("근처엔 없어서 6km 떨어진 성수 카페를 골랐어요."))
    r1 = svc.handle(ChatRequest(message="인사동 카페 추천해줘"))
    r2 = svc.handle(ChatRequest(session_id=r1.session_id, message="다른 데 더 추천해줘"))
    assert r2.answer == "근처엔 없어서 6km 떨어진 성수 카페를 골랐어요."


def test_more_only_far_places_template_when_llm_down(small_catalog):
    from app.schemas import ChatRequest
    from tests.conftest import FakeLLM

    svc = _far_service(_far_cafe_catalog(small_catalog), FakeLLM(fail=True))
    r1 = svc.handle(ChatRequest(message="인사동 카페 추천해줘"))
    r2 = svc.handle(ChatRequest(session_id=r1.session_id, message="다른 데 더 추천해줘"))
    assert r2.answer.startswith("인사동 근처(1.5km 안)에는 더 보여드릴 곳이 없어서 조금 떨어진 곳을 골랐어요.")
    assert "근처 추천 장소" not in r2.answer
    assert "km 떨어진" in r2.answer


def test_api_clarify_then_name_only(tmp_path):
    """API 멀티턴: 되묻기 뒤 장소 이름만 답하면 앞 질문(요금)에 답한다. 괄호 이름도 부르는 이름으로."""
    import dataclasses

    from app.catalog import load_catalog
    from app.llm import CLARIFY_ANSWER

    catalog = load_catalog(CATALOG_574, tmp_path / "none.json")
    sp = next(p for p in catalog.values() if p.title == "대원군별장(석파정)")
    catalog[sp.id] = dataclasses.replace(sp, tel="02-395-0100", detail={"contact": "02-395-0100"})
    client = TestClient(create_app(Deps(catalog=catalog, embedder=FakeEmbedder(),
                                        searcher=FakeSearcher(catalog, scores={sp.id: 3.0}),
                                        llm=FakeLLM(), history=InMemoryHistoryRepo())))

    def say(sid, message):
        r = client.post("/api/chat", json={"session_id": sid, "message": message})
        assert r.status_code == 200, r.text
        return r.json()

    r1 = say("s1", "종로 관광지 추천해줘")
    assert "대원군별장(석파정)" in [p["title"] for p in r1["places"]]
    r2 = say("s1", "석파정 무료 입장이야?")
    assert "요금 정보는 없어요" in r2["answer"] and "02-395-0100" in r2["answer"]

    assert say("s2", "종로 관광지 추천해줘")["places"]
    assert say("s2", "무료 입장이야?")["answer"] == CLARIFY_ANSWER
    r3 = say("s2", "대원군별장")
    assert r3["places"] == [] and r3["center"] is None
    assert "요금 정보는 없어요" in r3["answer"] and "02-395-0100" in r3["answer"]
