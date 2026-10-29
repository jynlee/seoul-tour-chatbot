"""QA 통합: B8(place_info)·B9(멀티턴) — 실제 OpenSearch(seoul-tour)·Ollama(gemma4:e4b)·MySQL(chat_message).

실행: pytest -m integration -v  (worktree 루트에 .env 필요)
대화 기록은 `test-qa-` 접두 세션만 쓰고 끝나면 지운다.
LLM 답변 문구는 매번 달라서, "어느 장소를 가리켰는지"는 /api/history 의 place_info 기록(center.label)으로 확인한다.
"""
import dataclasses
import uuid

import pytest

from app.catalog import CAFE_CAT3
from app.intent import matches_topic
from app.llm import CLARIFY_ANSWER, ORDINAL_OUT_OF_RANGE
from tests.conftest import FakeLLM

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live():
    from fastapi.testclient import TestClient

    from app.main import build_real_deps, create_app

    deps = build_real_deps()
    client = TestClient(create_app(deps))
    # Ollama 만 꺼진 상황: 나머지는 실제 그대로
    down = TestClient(create_app(dataclasses.replace(deps, llm=FakeLLM(fail=True))))
    sessions = []
    yield client, down, deps, sessions
    for sid in sessions:
        deps.history.delete_session(sid)


class Talk:
    def __init__(self, client, sessions):
        self.client = client
        self.sid = f"test-qa-{uuid.uuid4().hex[:12]}"
        sessions.append(self.sid)

    def say(self, message, **extra):
        r = self.client.post("/api/chat", json={"session_id": self.sid, "message": message, **extra})
        assert r.status_code == 200, r.text
        return r.json()

    def last_bot(self):
        return self.client.get(f"/api/history/{self.sid}").json()["messages"][-1]


def ids(body):
    return [p["id"] for p in body["places"]]


def assert_place_info(talk, body, title):
    """정보 질문 응답: 지도 유지 + 기록에는 설명한 장소가 center(source=place)로."""
    assert body["places"] == [] and body["center"] is None
    assert body["answer"].strip()
    bot = talk.last_bot()
    assert bot["places"] == []
    assert bot["center"]["source"] == "place" and bot["center"]["label"] == title


def test_live_session1_myeongdong(live):
    client, _, deps, sessions = live
    t = Talk(client, sessions)
    r1 = t.say("명동 맛집 추천해줘")
    assert r1["center"]["label"] == "명동" and r1["places"]
    r2 = t.say("카페는?")
    assert r2["center"]["label"] == "명동"
    assert r2["places"] and all(deps.catalog[i].cat3 == CAFE_CAT3 for i in ids(r2))

    r3 = t.say("다른 데 더 추천해줘")
    assert r3["places"], r3["answer"]
    assert r3["center"]["label"] == "명동"
    assert all(deps.catalog[i].cat3 == CAFE_CAT3 for i in ids(r3))
    assert not set(ids(r3)) & set(ids(r2))
    assert "남산" not in r3["answer"]  # 예전 버그: 답변에 다른 지역명('남산 근처')
    for title in (p["title"] for p in r2["places"]):
        assert title not in r3["answer"], f"이전 카페를 다시 말함: {title}"

    target = r3["places"][1] if len(r3["places"]) > 1 else r3["places"][0]
    r4 = t.say("두 번째 거기 어디야?" if len(r3["places"]) > 1 else "첫 번째 거기 어디야?")
    assert_place_info(t, r4, target["title"])


def test_live_session2_gangnam(live):
    client, _, _, sessions = live
    t = Talk(client, sessions)
    r1 = t.say("강남 관광지 알려줘")
    assert r1["center"]["source"] == "gu" and r1["center"]["label"] == "강남구"
    assert r1["places"] and all(p["kind"] == "tour" for p in r1["places"])
    first = r1["places"][0]

    r2 = t.say("아까 첫 번째 거 다시 알려줘")
    assert_place_info(t, r2, first["title"])

    r3 = t.say("거기서 가까운 맛집은?")
    assert r3["center"]["source"] == "place" and r3["center"]["label"] == first["title"]
    assert r3["places"] and all(p["kind"] == "food" for p in r3["places"])


def test_live_info_by_name_missing_field(live):
    """주차 정보가 없는 음식점(B7 574/574 기준 각시보쌈) → 지어내지 않고 전화 안내(LLM 호출 없이 고정 문구)."""
    client, _, deps, sessions = live
    p = next(p for p in deps.catalog.values() if p.title == "각시보쌈")
    assert not p.detail.get("parking") and p.tel
    t = Talk(client, sessions)
    r = t.say("각시보쌈 주차 가능해?")
    assert r["answer"] == f"각시보쌈 — 주차 정보는 없어요. 전화({p.tel})로 확인해 보세요."
    assert_place_info(t, r, "각시보쌈")


def test_live_info_by_name_with_value(live):
    """'고려삼계탕 주차 가능해?' — B7 완료 후 실데이터 주차 '가능'. 실제 LLM 답이 그 값과 어긋나지 않는지."""
    client, _, deps, sessions = live
    p = next(p for p in deps.catalog.values() if p.title == "고려삼계탕")
    assert p.detail.get("parking") == "가능"
    t = Talk(client, sessions)
    r = t.say("고려삼계탕 주차 가능해?")
    assert_place_info(t, r, "고려삼계탕")
    assert "주차" in r["answer"] and "불가" not in r["answer"] and "정보는 없" not in r["answer"]


def test_live_info_demonstrative_selected_and_first(live):
    client, _, _, sessions = live
    t = Talk(client, sessions)
    r1 = t.say("명동 맛집 추천해줘")
    assert len(r1["places"]) >= 2
    chosen = r1["places"][-1]
    r = t.say("거기 전화번호 알려줘", selected_place_id=chosen["id"])
    assert_place_info(t, r, chosen["title"])

    t2 = Talk(client, sessions)
    r1 = t2.say("명동 맛집 추천해줘")
    r = t2.say("거기 전화번호 알려줘")
    assert_place_info(t2, r, r1["places"][0]["title"])


def test_live_info_llm_down_uses_detail(live):
    """Ollama 만 꺼지면 detail 값을 그대로 쓴 템플릿 (가회동성당 주차: 가능)."""
    _, down, deps, sessions = live
    p = next(p for p in deps.catalog.values() if p.title == "가회동성당")
    t = Talk(down, sessions)
    r = t.say("가회동성당 주차 돼?")
    assert r["answer"] == f"가회동성당 — 주차: {p.detail['parking']}."
    assert_place_info(t, r, "가회동성당")


def test_live_info_no_target_asks_back(live):
    client, _, _, sessions = live
    t = Talk(client, sessions)
    r = t.say("주차 가능해?")
    assert r["answer"] == CLARIFY_ANSWER
    assert r["places"] == [] and r["center"] is None
    bot = t.last_bot()
    assert bot["center"] is None and bot["places"] == []


def test_live_regression_near_cafe_after_info(live):
    """정보 질문 다음 '거기 근처 카페'는 방금 설명한 장소 기준 카페 추천."""
    client, _, deps, sessions = live
    t = Talk(client, sessions)
    t.say("명동 맛집 추천해줘")
    t.say("고려삼계탕 주차 가능해?")
    r = t.say("거기 근처 카페 있어?")
    assert r["center"]["label"] == "고려삼계탕" and r["center"]["source"] == "place"
    assert r["places"] and all(deps.catalog[i].cat3 == CAFE_CAT3 for i in ids(r))


def test_live_qa4_palace_reference(live):
    """QA-4: 목록에 이름에 '궁'이 든 곳이 있으면 '아까 그 궁'은 그곳 (실측: 가회동성당·…·건청궁 순)."""
    client, _, _, sessions = live
    t = Talk(client, sessions)
    r1 = t.say("종로 역사 관광지")
    palaces = [p["title"] for p in r1["places"] if "궁" in p["title"]]
    if not palaces:
        pytest.skip(f"이번 검색 결과에 '궁'이 든 장소 없음: {[p['title'] for p in r1['places']]}")
    r = t.say("아까 그 궁 주차돼?")
    assert_place_info(t, r, palaces[0])


def test_live_qa5_qa6_out_of_range_and_no_target(live):
    client, _, _, sessions = live
    t = Talk(client, sessions)
    r1 = t.say("성수 카페")
    n = len(r1["places"])
    r = t.say(f"{n + 1}번째 거 어디야?")
    assert r["answer"] == ORDINAL_OUT_OF_RANGE.format(n=n)
    assert r["places"] == [] and r["center"] is None

    t2 = Talk(client, sessions)
    r = t2.say("거기 어디야?")
    assert r["answer"] == CLARIFY_ANSWER and r["places"] == []


@pytest.mark.parametrize("message", ["강서구에 산책할만한 곳 알려줘", "강서구 공원 추천해줘"])
def test_live_gu_nature_topic(live, message):
    """51b8c0d: 구 기준점은 구 전체에서, 산책·공원은 맞는 곳을 앞으로.

    데이터 확장(2026-10-27) 뒤 강서구 공원이 1곳 → 15곳 넘게 늘어 1번 고정 대신 '5곳 안에 강서습지생태공원,
    5곳 모두 산책·자연 주제'로 확인한다.
    """
    client, _, deps, sessions = live
    t = Talk(client, sessions)
    r = t.say(message)
    assert r["center"]["source"] == "gu" and r["center"]["label"] == "강서구"
    assert "강서습지생태공원" in [p["title"] for p in r["places"]], r["places"]
    assert all(matches_topic(p["category"], p["title"], "nature") for p in r["places"]), r["places"]
    assert {deps.catalog[i].gu for i in ids(r)} == {"강서구"}


def no_distance(body):
    return all(p["distance_m"] is None and p["walk_min"] is None for p in body["places"])


def test_live_qa8_gu_carried_turns_are_gu_without_distance(live):
    """QA-8 최종(5bed7dc·2fee772): 구 첫 턴·'다른 데 더'·'맛집은?' 모두 source=gu, 거리·도보 null."""
    client, _, deps, sessions = live
    t = Talk(client, sessions)
    r1 = t.say("강서구 공원 추천해줘")
    r2 = t.say("다른 데 더 추천해줘")
    r3 = t.say("맛집은?")
    for r in (r1, r2, r3):
        assert r["center"]["source"] == "gu" and r["center"]["label"] == "강서구", r["center"]
        assert r["places"] and no_distance(r), r["places"]
        assert {deps.catalog[i].gu for i in ids(r)} == {"강서구"}
    assert all(p["kind"] == "food" for p in r3["places"])


def test_live_qa8_area_carried_turn_keeps_history_and_distance(live):
    client, _, _, sessions = live
    t = Talk(client, sessions)
    t.say("명동 맛집 추천해줘")
    r = t.say("카페는?")
    assert r["center"]["source"] == "history" and r["center"]["label"] == "명동"
    assert r["places"] and all(isinstance(p["distance_m"], int) and isinstance(p["walk_min"], int)
                               for p in r["places"])


def test_live_topic_missing_and_hangang_food(live):
    client, _, _, sessions = live
    # 데이터 확장 뒤 금천구에도 공원이 생겨 산책 대신 야경(금천구 0곳)으로 확인
    r = Talk(client, sessions).say("금천구 야경 볼 곳")
    assert r["places"] and r["center"]["label"] == "금천구"
    assert any(w in r["answer"] for w in ("없", "못 찾", "어려", "아쉽")), r["answer"]  # 솔직히 안내
    r = Talk(client, sessions).say("한강 근처 맛집")
    assert r["places"] and all(p["kind"] == "food" for p in r["places"])


# ---------------------------------------------------------------- 2b4a42a: 괄호 이름·되묻기 뒤 이어받기 (실서비스)

def test_live_alias_clarify_explain_with_llm(live):
    """'거기 어디야?' → 되묻기 → '길상사' → 길상사(서울) 설명 (실제 Ollama·상세 정보)."""
    client, _, _, sessions = live
    t = Talk(client, sessions)
    assert t.say("거기 어디야?")["answer"] == CLARIFY_ANSWER
    r = t.say("길상사")
    assert_place_info(t, r, "길상사(서울)")
    assert "길상사" in r["answer"], r["answer"]


def test_live_alias_clarify_field_llm_down(live):
    """Ollama 꺼짐: '주차 가능해?' → 되묻기 → '세계태권도본부' → 국기원(세계태권도본부) 템플릿 답에 주차."""
    _, down, _, sessions = live
    t = Talk(down, sessions)
    assert t.say("주차 가능해?")["answer"] == CLARIFY_ANSWER
    r = t.say("세계태권도본부")
    assert_place_info(t, r, "국기원(세계태권도본부)")
    assert r["answer"].startswith("국기원(세계태권도본부) — 주차"), r["answer"]


@pytest.mark.parametrize("message, source, label", [
    ("남산 맛집", "area", "남산"),
    ("남산공원 근처 카페", "place", "남산공원(서울)"),
    ("kspo dome 근처 맛집", "place", "올림픽체조경기장(KSPO DOME)"),
])
def test_live_alias_center(live, message, source, label):
    client, _, _, sessions = live
    r = Talk(client, sessions).say(message)
    assert r["center"]["source"] == source and r["center"]["label"] == label, r["center"]
    assert r["places"]


def test_live_alias_not_names(live):
    client, _, _, sessions = live
    for message in ["서울 관광지 추천해줘", "실내 관광지 추천해줘", "공기 좋은 산책 코스 추천해줘"]:
        r = Talk(client, sessions).say(message)
        assert r["center"] is None or r["center"]["source"] != "place", (message, r["center"])


# ---------------------------------------------------------------- QA-9 (c9cace1·de019c1): 구 안에 0~2곳이어도 거리 null + 다른 구 안내

def tells_other_gu(answer, gus):
    return "다른 구" in answer or any(g in answer for g in gus)


# 데이터 확장(2026-10-27) 뒤 강서구에 카페가 9곳 생겨, 카페 0곳인 양천구로 확인
@pytest.mark.parametrize("turns", [["양천구 카페 추천해줘"], ["양천구 공원 추천해줘", "카페는?"]])
def test_live_qa9_gu_empty(live, turns):
    client, _, deps, sessions = live
    t = Talk(client, sessions)
    for m in turns:
        r = t.say(m)
    assert r["center"]["source"] == "gu" and r["center"]["label"] == "양천구"
    assert len(r["places"]) >= 3 and no_distance(r), r["places"]
    gus = {deps.catalog[i].gu for i in ids(r)}
    assert "양천구" not in gus
    assert tells_other_gu(r["answer"], gus), r["answer"]


def test_live_qa9_gu_fill_and_enough(live):
    client, _, deps, sessions = live
    # 데이터 확장 뒤 금천구 맛집이 3곳 넘게 늘어, 카페 1곳인 노원구로 '구 안 1곳 + 다른 구 채우기' 확인
    r = Talk(client, sessions).say("노원구 카페 추천해줘")
    gus = [deps.catalog[i].gu for i in ids(r)]
    assert r["center"]["source"] == "gu" and no_distance(r)
    assert gus[0] == "노원구" and len(gus) == 3, gus
    assert tells_other_gu(r["answer"], set(gus) - {"노원구"}), r["answer"]
    r = Talk(client, sessions).say("강남구 맛집 추천해줘")
    assert no_distance(r) and {deps.catalog[i].gu for i in ids(r)} == {"강남구"}
    assert "다른 구" not in r["answer"], r["answer"]
