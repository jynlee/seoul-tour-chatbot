"""QA: B8(장소 정보 질문 place_info) + B9(멀티턴) — POST /api/chat·GET /api/history (가짜 의존성 + 실제 카탈로그 574곳).

세션1·2는 리드 재현 시나리오. 정보 질문은 이름/거기+선택/거기+직전 첫 장소/정보 없음/LLM 다운/대상 없음.
"""
import dataclasses

import pytest
from fastapi.testclient import TestClient

from app.catalog import CAFE_CAT3, load_catalog
from app.chat import Deps
from app.history import InMemoryHistoryRepo
from app.llm import CLARIFY_ANSWER, NO_MORE_ANSWER
from app.main import create_app
from tests.conftest import SMALL_PLACES, FakeEmbedder, FakeLLM, FakeSearcher

GOREO = "고려삼계탕"
GAESEONG = "개성만두 궁"


@pytest.fixture(scope="module")
def real_catalog(tmp_path_factory):
    """실제 카탈로그(상세 정보 없이) + 시험용 detail: 고려삼계탕은 주차 정보 없음, 개성만두 궁은 주차 '불가능'."""
    catalog = load_catalog("data/seoul_tour.json", tmp_path_factory.mktemp("qa") / "none.json")
    by_title = {p.title: p for p in catalog.values()}
    gs = by_title[GOREO]
    catalog[gs.id] = dataclasses.replace(gs, tel="02-752-9376", detail={"hours": "10:00~22:00", "menu": "삼계탕"})
    gm = by_title[GAESEONG]
    catalog[gm.id] = dataclasses.replace(gm, tel="02-733-9240", detail={"parking": "불가능"})
    return catalog


class Api:
    """한 세션으로 /api/chat 을 이어서 부르는 도우미."""

    def __init__(self, catalog, llm=None):
        self.catalog = catalog
        self.llm = llm or FakeLLM("가짜 답변이에요.")
        self.deps = Deps(catalog=catalog, embedder=FakeEmbedder(), searcher=FakeSearcher(catalog),
                         llm=self.llm, history=InMemoryHistoryRepo())
        self.client = TestClient(create_app(self.deps))
        self.sid = None

    def say(self, message, **extra):
        body = {"message": message, **extra}
        if self.sid:
            body["session_id"] = self.sid
        r = self.client.post("/api/chat", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        self.sid = data["session_id"]
        return data

    def history(self):
        return self.client.get(f"/api/history/{self.sid}").json()["messages"]

    def id_of(self, title):
        return next(p.id for p in self.catalog.values() if p.title == title)

    def last_prompt(self):
        return self.llm.prompts[-1]


def ids(body):
    return [p["id"] for p in body["places"]]


def is_cafe(catalog, body):
    return bool(body["places"]) and all(catalog[p["id"]].cat3 == CAFE_CAT3 for p in body["places"])


def assert_place_info(body):
    """정보 질문 응답: 지도 유지(places=[], center=null)."""
    assert body["places"] == [] and body["center"] is None
    assert body["answer"].strip()


# ---------------------------------------------------------------- 세션1: 명동

def test_session1_myeongdong_full_flow(real_catalog):
    api = Api(real_catalog)
    r1 = api.say("명동 맛집 추천해줘")
    assert r1["center"]["label"] == "명동" and r1["center"]["source"] == "area"
    assert r1["places"] and all(p["kind"] == "food" for p in r1["places"])

    r2 = api.say("카페는?")
    assert r2["center"]["label"] == "명동"
    assert is_cafe(real_catalog, r2)

    r3 = api.say("다른 데 더 추천해줘")
    assert r3["center"]["label"] == "명동"  # 지역 유지 (예전엔 남산으로 바뀜)
    assert is_cafe(real_catalog, r3)  # 카테고리 유지 (예전엔 관광지로 바뀜)
    assert not set(ids(r3)) & set(ids(r2))  # 이전과 겹치지 않음
    # 답변 지역명 = center.label: 프롬프트의 기준점이 명동, 다른 지역을 쓰지 말라는 규칙
    prompt = api.last_prompt()
    assert "[기준점]\n명동\n" in prompt
    assert "'명동'만 쓰고" in prompt

    n = len(api.llm.prompts)
    r4 = api.say("두 번째 거기 어디야?")
    assert_place_info(r4)
    assert len(api.llm.prompts) == n + 1
    assert f"이름: {r3['places'][1]['title']}" in api.last_prompt()


def test_session1_more_template_uses_center_label(real_catalog):
    """LLM 다운이어도 '다른 데 더' 답변의 지역명은 center.label."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    api.say("명동 맛집 추천해줘")
    api.say("카페는?")
    r3 = api.say("다른 데 더 추천해줘")
    assert r3["answer"].startswith(f"{r3['center']['label']} 근처 추천 장소를 지도에 표시했어요")
    assert "남산" not in r3["answer"]


def test_session1_ordinal_info_keeps_pins_on_history(real_catalog):
    """'두 번째 거기 어디야?' 뒤 새로고침해도 핀 복원 기준(places 있는 마지막 봇 메시지)은 r3 그대로."""
    api = Api(real_catalog)
    api.say("명동 맛집 추천해줘")
    api.say("카페는?")
    r3 = api.say("다른 데 더 추천해줘")
    api.say("두 번째 거기 어디야?")
    bots_with_places = [m for m in api.history() if m["role"] == "assistant" and m["places"]]
    assert [p["id"] for p in bots_with_places[-1]["places"]] == ids(r3)


def test_more_exhausted_says_no_more(real_catalog):
    """작은 카탈로그에서 카페를 다 보여 주면 솔직하게 '더 보여드릴 곳이 없어요'."""
    small = {p.id: p for p in SMALL_PLACES}
    api = Api(small)
    r1 = api.say("광화문 근처 카페")
    assert r1["places"]
    seen = set(ids(r1))
    for _ in range(3):
        r = api.say("다른 데 더 추천해줘")
        if not r["places"]:
            break
        assert not set(ids(r)) & seen
        seen |= set(ids(r))
    assert r["places"] == [] and r["center"] is None
    assert r["answer"] == NO_MORE_ANSWER.format(label="광화문 근처")


# ---------------------------------------------------------------- 세션2: 강남

def test_session2_gangnam_full_flow(real_catalog):
    api = Api(real_catalog)
    r1 = api.say("강남 관광지 알려줘")
    assert r1["center"]["source"] == "gu" and r1["center"]["label"] == "강남구"
    assert r1["places"] and all(p["kind"] == "tour" for p in r1["places"])

    n = len(api.llm.prompts)
    r2 = api.say("아까 첫 번째 거 다시 알려줘")
    assert_place_info(r2)
    assert len(api.llm.prompts) == n + 1
    assert f"이름: {r1['places'][0]['title']}" in api.last_prompt()

    r3 = api.say("거기서 가까운 맛집은?")
    assert r3["center"]["source"] == "place"
    assert r3["center"]["label"] == r1["places"][0]["title"]  # 방금 설명한 1번 장소 기준
    assert r3["places"] and all(p["kind"] == "food" for p in r3["places"])
    assert r1["places"][0]["id"] not in ids(r3)


# ---------------------------------------------------------------- B8 정보 질문

def test_info_by_name_without_field_value(real_catalog):
    """'고려삼계탕 주차 가능해?' — 주차 정보가 없으면 LLM 없이 '없어요' + 전화 안내(지어내지 않음)."""
    api = Api(real_catalog)
    api.say("명동 맛집 추천해줘")
    n = len(api.llm.prompts)
    r = api.say("고려삼계탕 주차 가능해?")
    assert_place_info(r)
    assert r["answer"] == "고려삼계탕 — 주차 정보는 없어요. 전화(02-752-9376)로 확인해 보세요."
    assert len(api.llm.prompts) == n


def test_info_by_name_first_turn(real_catalog):
    """추천 없이 첫 질문으로 이름을 말해도 카탈로그에서 찾는다."""
    api = Api(real_catalog)
    r = api.say("고려삼계탕 몇 시에 열어?")
    assert_place_info(r)
    prompt = api.last_prompt()
    assert "이름: 고려삼계탕" in prompt and "10:00~22:00" in prompt


def test_info_demonstrative_with_selected_place(real_catalog):
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    r1 = api.say("명동 맛집 추천해줘")
    gm = api.id_of(GAESEONG)
    assert gm in ids(r1) and ids(r1)[0] != gm  # 첫 장소가 아닌 곳을 골라야 '선택'이 검증됨
    r = api.say("거기 주차 돼?", selected_place_id=gm)
    assert_place_info(r)
    assert r["answer"] == "개성만두 궁 — 주차: 불가능."


def test_info_demonstrative_falls_back_to_first_place(real_catalog):
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    r1 = api.say("명동 맛집 추천해줘")
    r = api.say("거기 전화번호 알려줘")
    assert_place_info(r)
    assert r["answer"].startswith(f"{r1['places'][0]['title']} — ")


def test_info_demonstrative_unknown_selected_id_falls_back(real_catalog):
    """목록에 없는 selected_place_id 가 와도 500 없이 직전 첫 장소로."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    r1 = api.say("명동 맛집 추천해줘")
    r = api.say("거기 전화번호 알려줘", selected_place_id="no-such-id")
    assert_place_info(r)
    assert r["answer"].startswith(f"{r1['places'][0]['title']} — ")


def test_info_field_missing_and_no_tel(real_catalog):
    """정보도 전화번호도 없으면 전화 안내 없이 '정보는 없어요'만."""
    catalog = dict(real_catalog)
    gs = next(p for p in catalog.values() if p.title == GOREO)
    catalog[gs.id] = dataclasses.replace(gs, tel="", detail={})
    api = Api(catalog)
    r = api.say("고려삼계탕 주차 가능해?")
    assert r["answer"] == "고려삼계탕 — 주차 정보는 없어요."
    assert api.llm.prompts == []


def test_info_llm_down_uses_detail_template(real_catalog):
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    api.say("명동 맛집 추천해줘")
    r = api.say("고려삼계탕 몇 시에 열어?")
    assert_place_info(r)
    assert r["answer"] == "고려삼계탕 — 이용 시간: 10:00~22:00."


def test_info_llm_down_partial_fields(real_catalog):
    """여러 항목 중 일부만 있으면 있는 값 + '없어요' + 전화 안내."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    r = api.say("고려삼계탕 메뉴랑 주차 알려줘")
    assert r["answer"] == "고려삼계탕 — 주차 정보는 없어요 / 메뉴: 삼계탕. 전화(02-752-9376)로 확인해 보세요."


def test_info_llm_down_explain_only(real_catalog):
    """'어디야'처럼 항목 없이 설명만 물으면 기본 정보 템플릿."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    r1 = api.say("명동 맛집 추천해줘")
    r = api.say("두 번째 거 어디야?")
    p = real_catalog[r1["places"][1]["id"]]
    assert r["answer"].startswith(f"{p.title}: {p.category}, 주소 {p.addr}")


@pytest.mark.parametrize("message", ["주차 가능해?", "거기 몇 시에 열어?"])
def test_info_no_target_asks_back(real_catalog, message):
    api = Api(real_catalog)
    r = api.say(message)
    assert_place_info(r)
    assert r["answer"] == CLARIFY_ANSWER
    assert api.llm.prompts == []


def test_info_then_demonstrative_points_to_explained_place(real_catalog):
    """정보 질문 다음 '거기'는 방금 설명한 장소 (직전 첫 장소가 아님)."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    r1 = api.say("명동 맛집 추천해줘")
    assert ids(r1)[0] != api.id_of(GAESEONG)
    api.say("개성만두 궁 주차 돼?")
    r = api.say("거기 몇 시에 열어?")
    assert r["answer"].startswith("개성만두 궁 — ")


# ---------------------------------------------------------------- 회귀

def test_regression_demonstrative_near_cafe(real_catalog):
    """'거기 근처 카페'는 정보 질문이 아니라 선택한 장소 기준 카페 추천."""
    api = Api(real_catalog)
    api.say("명동 맛집 추천해줘")
    gm = api.id_of(GAESEONG)
    r = api.say("거기 근처 카페 있어?", selected_place_id=gm)
    assert r["center"]["label"] == GAESEONG and r["center"]["source"] == "place"
    assert is_cafe(real_catalog, r)
    assert gm not in ids(r)


def test_regression_exit_number_is_not_ordinal(real_catalog):
    """'3번 출구'는 순서 지칭이 아님 → 추천."""
    api = Api(real_catalog)
    api.say("명동 맛집 추천해줘")
    r = api.say("명동역 3번 출구 근처 카페")
    assert r["center"]["label"] == "명동"
    assert is_cafe(real_catalog, r)


def test_regression_casual_after_list(real_catalog):
    api = Api(real_catalog)
    api.say("명동 맛집 추천해줘")
    r = api.say("고마워!")
    assert r["places"] == [] and r["center"] is None


# ---------------------------------------------------------------- /api/history 형식

def test_history_place_info_message_format(real_catalog):
    api = Api(real_catalog)
    r1 = api.say("명동 맛집 추천해줘")
    r2 = api.say("두 번째 거 어디야?")
    msgs = api.history()
    assert [m["role"] for m in msgs] == ["user", "assistant"] * 2
    bot = msgs[3]
    assert bot["message"] == r2["answer"]
    assert bot["places"] == []
    second = r1["places"][1]
    assert bot["center"]["source"] == "place"
    assert bot["center"]["label"] == second["title"]
    assert (bot["center"]["lat"], bot["center"]["lng"]) == (second["lat"], second["lng"])


def test_history_clarify_and_no_more_saved_without_center(real_catalog):
    """되묻기는 설명한 장소가 없으니 기록도 center:null, places:[]."""
    api = Api(real_catalog)
    api.say("주차 가능해?")
    bot = api.history()[1]
    assert bot["center"] is None and bot["places"] == []
