"""통합: 추천 코스 실데이터(seoul-tour, 3,441곳) 확인 — 실제 OpenSearch·임베딩으로 코스가 쓸 만한지.

실행: pytest -m integration tests/integration/test_live_course.py
LLM은 가짜(답 문구는 안 봄, 뺀 칸 안내는 핸들러가 앞에 붙인 문구로 확인). 대화 기록은 `test-qa-` 세션만 쓰고 끝나면 지운다.
"""
import dataclasses

import pytest

from app.course import MAX_TOTAL_WALK_M, WIDE_RADIUS_M
from app.geo import haversine_m
from app.llm import COURSE_CAFE_DROPPED, COURSE_HOURS_NOTE
from app.recommend import group_key
from tests.conftest import FakeLLM
from tests.integration.test_live_multiturn import Talk

pytestmark = pytest.mark.integration

QUESTIONS = ["종로 데이트 코스", "명동 쇼핑하고 맛집 코스", "성수 코스 짜줘", "홍대 근처 데이트 추천해줘", "여의도 데이트 코스"]


@pytest.fixture(scope="module")
def live():
    from fastapi.testclient import TestClient

    from app.main import build_real_deps, create_app

    deps = dataclasses.replace(build_real_deps(), llm=FakeLLM("가짜 답변이에요."))
    client = TestClient(create_app(deps))
    sessions = []
    yield client, deps, sessions
    for sid in sessions:
        deps.history.delete_session(sid)


@pytest.fixture(scope="module")
def courses(live):
    client, _deps, sessions = live
    return {q: Talk(client, sessions).say(q) for q in QUESTIONS}


def test_print_courses(courses):
    """사람이 보는 용: -s 로 돌리면 실제 코스가 찍힌다."""
    for q, r in courses.items():
        print(f"\n## {q}  (center={r['center'] and r['center']['label']})")
        for p in r["places"]:
            print(f"  {p['step']} | {p['title']} | leg {p['leg_m']}m / {p['leg_walk_min']}분")
        print(f"  answer: {r['answer'][:80]}")


@pytest.mark.parametrize("q", QUESTIONS)
def test_course_shape(courses, q):
    r = courses[q]
    assert r["course"] is True
    places = r["places"]
    assert 3 <= len(places) <= 4, [p["title"] for p in places]
    legs = [haversine_m(a["lat"], a["lng"], b["lat"], b["lng"]) for a, b in zip(places, places[1:])]
    assert all(d <= WIDE_RADIUS_M + 1 for d in legs), legs
    assert sum(legs) <= MAX_TOTAL_WALK_M + 1, legs
    assert r["answer"].rstrip().endswith(COURSE_HOURS_NOTE)


@pytest.mark.parametrize("q", QUESTIONS)
def test_course_no_same_group(courses, q):
    # 음식점끼리는 같은 이름 앞머리를 가질 수 있다(Ruling 6) — 관광지 쌍만 본다
    tours = [p for p in courses[q]["places"] if p["kind"] != "food"]
    keys = [group_key(p["title"]) for p in tours]
    keys = [k for k in keys if k]
    assert len(keys) == len(set(keys)), [p["title"] for p in tours]
    ids = [p["id"] for p in courses[q]["places"]]
    assert len(ids) == len(set(ids))


def test_shopping_course_has_shopping(courses, live):
    _client, deps, _s = live
    r = courses["명동 쇼핑하고 맛집 코스"]
    assert any(deps.catalog[p["id"]].content_type == "38" for p in r["places"]), [p["title"] for p in r["places"]]


def test_yeouido_cafe_dropped(courses):
    r = courses["여의도 데이트 코스"]
    assert "카페" not in [p["step"] for p in r["places"]]
    assert COURSE_CAFE_DROPPED in r["answer"]
