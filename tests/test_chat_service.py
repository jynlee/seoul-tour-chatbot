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
