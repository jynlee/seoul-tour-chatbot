"""추천 코스 API: POST /api/chat 이 코스(course=True, 칸 순서 places)를 돌려주는지 (가짜 의존성).

종로(인사동·삼청동 근처)에 볼거리·맛집·카페를 두 벌씩 더한 카탈로그로, 데이트 코스가 두 번(처음·"다른 코스") 나오게 한다.
"""
import pytest
from fastapi.testclient import TestClient

from app.catalog import CAFE_CAT3
from app.chat import Deps
from app.history import InMemoryHistoryRepo
from app.llm import COURSE_FAIL_NOTICE, COURSE_HOURS_NOTE, display_title
from app.main import create_app
from tests.api.conftest import BAD_COORD_PLACE
from tests.conftest import SMALL_PLACES, FakeEmbedder, FakeLLM, FakeSearcher, _p


def _sight(id, title, lat, lng):
    return _p(id, title, "12", "역사관광지", "A02010100", "서울특별시 종로구 a", lat, lng, "종로구", tel="02-100-0000")


def _food(id, title, lat, lng):
    return _p(id, title, "39", "한식", "A05020100", "서울특별시 종로구 b", lat, lng, "종로구", tel="02-200-0000")


def _cafe(id, title, lat, lng):
    return _p(id, title, "39", "카페/전통찻집", CAFE_CAT3, "서울특별시 종로구 c", lat, lng, "종로구", tel="02-300-0000")


# 인사동·삼청동 근처, 서로 걸어서 800m 안팎
COURSE_EXTRA = [
    _sight("c-s1", "운현궁", 37.5765, 126.9867),
    _sight("c-s2", "탑골공원", 37.5711, 126.9883),
    _food("c-f1", "인사동 한정식", 37.5745, 126.9860),
    _food("c-f2", "삼청 칼국수", 37.5790, 126.9810),
    _cafe("c-c1", "감나무 찻집", 37.5735, 126.9865),
    _cafe("c-c2", "돌담 카페", 37.5795, 126.9815),
]

# 코스가 딱 한 벌만 나오는 카탈로그 (종로 볼거리·맛집·카페 하나씩)
ONE_COURSE = [
    _sight("o-s1", "운현궁", 37.5765, 126.9867),
    _food("o-f1", "인사동 한정식", 37.5745, 126.9860),
    _cafe("o-c1", "감나무 찻집", 37.5735, 126.9865),
]


@pytest.fixture
def catalog():
    return {p.id: p for p in SMALL_PLACES + [BAD_COORD_PLACE] + COURSE_EXTRA}


def _client(catalog, llm=None, searcher=None):
    deps = Deps(catalog=catalog, embedder=FakeEmbedder(), searcher=searcher or FakeSearcher(catalog),
                llm=llm or FakeLLM("코스를 골라봤어요."), history=InMemoryHistoryRepo())
    return TestClient(create_app(deps)), deps


def say(client, message, sid, **extra):
    r = client.post("/api/chat", json={"message": message, "session_id": sid, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_date_question_returns_course(client):
    data = say(client, "종로 데이트 추천해줘", "test-course-1")
    assert data["course"] is True
    assert 3 <= len(data["places"]) <= 4
    assert all(p["step"] for p in data["places"])
    assert [p["step"] for p in data["places"]][:3] == ["볼거리", "맛집", "카페"]
    assert data["answer"].endswith(COURSE_HOURS_NOTE)
    assert data["center"]["label"] == "종로구"


def test_date_cafe_question_stays_list(client):
    data = say(client, "종로 데이트하기 좋은 카페", "test-course-2")
    assert data["course"] is False
    assert data["places"]
    assert all(p["step"] is None for p in data["places"])


def test_ordinal_after_course(client, deps):
    course = say(client, "종로 데이트 추천해줘", "test-course-3")
    second = course["places"][1]
    data = say(client, "2번 거기 전화번호", "test-course-3")
    assert data["places"] == []
    assert data["course"] is False
    assert display_title(second["title"]) in deps.llm.prompts[-1]


def test_more_course_excludes_shown(client):
    first = say(client, "종로 데이트 추천해줘", "test-course-4")
    data = say(client, "다른 코스", "test-course-4")
    assert data["course"] is True
    assert len(data["places"]) >= 3
    assert all(p["step"] for p in data["places"])
    assert not {p["id"] for p in first["places"]} & {p["id"] for p in data["places"]}
    assert data["center"]["label"] == "종로구"


def test_more_course_twice_keeps_first_question(client):
    # 두 번째 "다른 코스"도 처음 질문(데이트)으로 다시 짠다 — 직전 "다른 코스"로 짜면 기본 코스(관광지…)가 된다
    first = say(client, "종로 데이트 추천해줘", "test-course-11")
    second = say(client, "다른 코스", "test-course-11")
    third = say(client, "또 다른 코스 없어?", "test-course-11")
    assert third["course"] is True
    assert third["places"][0]["step"] == "볼거리"
    shown = {p["id"] for p in first["places"] + second["places"]}
    assert not shown & {p["id"] for p in third["places"]}


def test_more_course_exhausted():
    client, _ = _client({p.id: p for p in ONE_COURSE})
    first = say(client, "종로 데이트 추천해줘", "test-course-5")
    assert first["course"] is True
    data = say(client, "다른 코스 보여줘", "test-course-5")
    assert data["course"] is False
    assert data["places"] == []
    assert "더 보여드릴 곳이 없어요" in data["answer"]
    assert data["answer"].startswith("종로구 근처")


def test_single_question_after_course_is_list(client):
    say(client, "종로 데이트 추천해줘", "test-course-6")
    data = say(client, "그 근처 카페", "test-course-6")
    assert data["course"] is False
    assert data["places"]
    assert all(p["step"] is None for p in data["places"])


def test_course_fail_falls_back(client):
    # 성동구에는 카페 하나뿐 → 코스를 못 짜고 일반 관광 추천
    data = say(client, "성동구 데이트 코스 짜줘", "test-course-7")
    assert data["course"] is False
    assert data["answer"].startswith(COURSE_FAIL_NOTICE.format(where="성동구에서는 "))
    assert data["places"]
    assert all(p["step"] is None for p in data["places"])


def test_course_llm_down_template(catalog):
    client, _ = _client(catalog, llm=FakeLLM(fail=True))
    data = say(client, "종로 데이트 추천해줘", "test-course-8")
    assert data["course"] is True
    assert data["answer"].startswith("코스를 짜 봤어요: 1.")
    assert data["answer"].endswith(COURSE_HOURS_NOTE)


def test_course_search_down_503(catalog):
    client, _ = _client(catalog, searcher=FakeSearcher(catalog, fail=True))
    r = client.post("/api/chat", json={"message": "종로 데이트 추천해줘", "session_id": "test-course-9"})
    assert r.status_code == 503


def test_course_saved_in_history(client):
    data = say(client, "종로 데이트 추천해줘", "test-course-10")
    hist = client.get("/api/history/test-course-10").json()["messages"]
    bot = hist[-1]
    assert bot["role"] == "assistant"
    assert bot["places"][0]["step"] == data["places"][0]["step"] == "볼거리"
    assert [p["id"] for p in bot["places"]] == [p["id"] for p in data["places"]]
