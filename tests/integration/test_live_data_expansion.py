"""QA 통합: 데이터 확장(seoul-tour-v3) 품질 메모 ①② 재현 — 실제 OpenSearch·임베딩 순위로만 드러나는 것.

실행: OPENSEARCH_INDEX=seoul-tour-v3 pytest -m integration tests/integration/test_live_data_expansion.py
LLM은 가짜(답 문구는 안 봄). 대화 기록은 `test-qa-` 세션만 쓰고 끝나면 지운다.
②는 0c2f9d3, ①은 02fee94(반경 안 kNN + 가장 가까운 곳 포함)에서 고쳐져 xfail을 지움 — 이제 회귀 테스트.
"""
import dataclasses

import pytest

from app.catalog import has_coords
from app.geo import haversine_m
from app.recommend import group_key
from tests.conftest import FakeLLM
from tests.integration.test_live_multiturn import Talk

pytestmark = pytest.mark.integration


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


def say(live, message):
    client, _deps, sessions = live
    return Talk(client, sessions).say(message)


# ① 반경 안 가장 가까운 곳이 kNN 상위 100곳 밖이면 빠짐 (청계천 84m 더 우리곱창 = kNN 261위, 1번은 890m 카페 빠우)
def test_live_q1_nearest_food_included(live):
    _client, deps, _s = live
    r = say(live, "청계천 근처 맛집 추천해줘")
    c = r["center"]
    assert c["label"] == "청계천"
    nearest = min((p for p in deps.catalog.values() if p.kind == "food" and has_coords(p)),
                  key=lambda p: haversine_m(c["lat"], c["lng"], p.lat, p.lng))
    assert nearest.id in [p["id"] for p in r["places"]], nearest.title


# ① 같은 원인: "남산 관광지"에 남산서울타워(32m, kNN 10위)가 5곳 밖
def test_live_q1_namsan_tower(live):
    r = say(live, "남산 관광지")
    assert r["center"]["label"] == "남산"
    assert "남산서울타워" in [p["title"] for p in r["places"]]


# ② (0c2f9d3에서 고침) 기준점 장소의 세부 장소가 결과에 나오던 문제 ("덕수궁 근처" 1번 덕수궁 돈덕전 0m, "반포한강공원 근처" 반포한강공원 달빛광장)
@pytest.mark.parametrize("message", ["덕수궁 근처 볼거리", "반포한강공원 근처 관광지"])
def test_live_q2_center_parts_excluded(live, message):
    r = say(live, message)
    key = group_key(r["center"]["label"])
    assert key and not [p["title"] for p in r["places"] if group_key(p["title"]) == key]


# ② (0c2f9d3에서 고침, 창덕궁이 기준점이 되어 세부 장소 제외) 묶기: 같은 궁의 세부 장소가 500m 넘게 떨어지면 한 목록에 둘 (창덕궁 다래나무·향나무 800m)
def test_live_q2_one_changdeokgung_part(live):
    r = say(live, "창덕궁 근처 관광지")
    parts = [p["title"] for p in r["places"] if group_key(p["title"]) == "창덕궁"]
    assert len(parts) <= 1, parts
