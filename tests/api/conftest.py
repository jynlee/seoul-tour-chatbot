"""Q1 API 테스트 공통 픽스처: 가짜 의존성으로 만든 FastAPI 앱."""
import pytest
from fastapi.testclient import TestClient

from app.chat import Deps
from app.history import InMemoryHistoryRepo
from app.main import create_app
from tests.conftest import SMALL_PLACES, FakeEmbedder, FakeLLM, FakeSearcher, _p

# 좌표가 서울 범위 밖으로 잘못 들어간 장소 (실데이터의 계남근린공원 등과 같은 (19.69, 117.99))
BAD_COORD_ID = "8888888"
BAD_COORD_PLACE = _p(BAD_COORD_ID, "잘못된좌표 맛집", "39", "한식", "A05020100",
                     "서울특별시 종로구 세종대로 1", 19.69, 117.99, "종로구")
ZERO_COORD_ID = "9999999"  # 도심속 바다축제 (0, 0)


@pytest.fixture
def catalog():
    return {p.id: p for p in SMALL_PLACES + [BAD_COORD_PLACE]}


@pytest.fixture
def deps(catalog):
    return Deps(catalog=catalog, embedder=FakeEmbedder(), searcher=FakeSearcher(catalog),
                llm=FakeLLM("추천 장소를 골라봤어요."), history=InMemoryHistoryRepo())


@pytest.fixture
def client(deps):
    return TestClient(create_app(deps))


def chat(client, message, **extra):
    """POST /api/chat → (status, json)."""
    r = client.post("/api/chat", json={"message": message, **extra})
    return r.status_code, r.json()
