"""QA: B8(장소 정보 질문 place_info) + B9(멀티턴) — POST /api/chat·GET /api/history (가짜 의존성 + 실제 카탈로그 574곳).

세션1·2는 리드 재현 시나리오. 정보 질문은 이름/거기+선택/거기+직전 첫 장소/정보 없음/LLM 다운/대상 없음.
"""
import dataclasses

import pytest
from fastapi.testclient import TestClient

from app.catalog import CAFE_CAT3, load_catalog
from app.chat import Deps
from app.geo import haversine_m
from app.history import InMemoryHistoryRepo
from app.intent import matches_topic
from app.llm import (
    CLARIFY_ANSWER, FAR_MORE_NOTICE, GU_EMPTY_MORE_NOTICE, GU_EMPTY_NOTICE, GU_FILL_MORE_NOTICE, GU_FILL_NOTICE,
    NO_MORE_ANSWER, ORDINAL_OUT_OF_RANGE, TOPIC_MISSING_NOTICE,
)
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
    """LLM 다운이어도 '다른 데 더' 답변의 지역명은 center.label.
    명동 카페는 1.5km 안이 3곳뿐 → 두 번째 목록은 모두 멀어서 먼 곳 안내가 앞에 붙고 '근처 추천' 문구는 안 씀."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    api.say("명동 맛집 추천해줘")
    api.say("카페는?")
    r3 = api.say("다른 데 더 추천해줘")
    assert all(p["distance_m"] > 1500 for p in r3["places"])
    assert r3["answer"].startswith(FAR_MORE_NOTICE.format(label=r3["center"]["label"]) + " 추천 장소를 지도에 표시했어요")
    assert "남산" not in r3["answer"]


def test_more_far_notice_added_when_llm_omits_it(real_catalog):
    """LLM 답에 '떨어/멀/km'가 없으면 먼 곳 안내를 앞에 붙이고, 있으면 두 번 붙이지 않는다."""
    api = Api(real_catalog, llm=FakeLLM("새 카페를 골라봤어요."))
    api.say("명동 맛집 추천해줘")
    api.say("카페는?")
    r3 = api.say("다른 데 더 추천해줘")
    assert r3["answer"] == FAR_MORE_NOTICE.format(label="명동") + " 새 카페를 골라봤어요."
    assert "'명동' 1.5km 안에는 더 보여드릴 곳이 없어서" in api.last_prompt()

    api2 = Api(real_catalog, llm=FakeLLM("명동에서 조금 떨어진 카페예요."))
    api2.say("명동 맛집 추천해줘")
    api2.say("카페는?")
    r3 = api2.say("다른 데 더 추천해줘")
    assert r3["answer"] == "명동에서 조금 떨어진 카페예요."


def test_more_near_results_have_no_far_notice(real_catalog):
    """첫 추천(다른 데 더 아님)에는 먼 곳 안내가 붙지 않는다."""
    api = Api(real_catalog, llm=FakeLLM("가짜 답변이에요."))
    r = api.say("명동 맛집 추천해줘")
    assert r["answer"] == "가짜 답변이에요."


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


# ---------------------------------------------------------------- QA-4~7 재확인 (팀원1 733af89)

def test_qa4_category_word_in_title_wins(real_catalog):
    """QA-4: '아까 그 궁' → 이름에 '궁'이 든 장소(건청궁), 같은 분류의 첫 장소(가회동성당) 아님."""
    api = Api(real_catalog)
    r1 = api.say("종로 관광지")
    titles = [p["title"] for p in r1["places"]]
    assert "건청궁" in titles and titles[0] != "건청궁"
    r = api.say("아까 그 궁 주차돼?")
    assert_place_info(r)
    assert api.history()[-1]["center"]["label"] == "건청궁"


def test_qa4_gunggeum_is_not_palace(real_catalog):
    """'궁금'의 '궁'은 분류 단어가 아님 → '궁금한데 아까 그 성당'은 가회동성당."""
    api = Api(real_catalog)
    api.say("종로 관광지")
    api.say("궁금한데 아까 그 성당 주차돼?")
    assert api.history()[-1]["center"]["label"] == "가회동성당"


@pytest.mark.parametrize("message", ["6번째 거 어디야?", "여섯 번째 거 어디야?", "10번 어디야?"])
def test_qa5_ordinal_out_of_range(real_catalog, message):
    api = Api(real_catalog)
    r1 = api.say("성수 카페")
    n = len(r1["places"])
    assert n == 5
    r = api.say(message)
    assert r["answer"] == ORDINAL_OUT_OF_RANGE.format(n=n)
    assert r["places"] == [] and r["center"] is None
    # 핀 복원 기준은 그대로
    bots = [m for m in api.history() if m["role"] == "assistant" and m["places"]]
    assert [p["id"] for p in bots[-1]["places"]] == ids(r1)


@pytest.mark.parametrize("first", [None, "주차 가능해?"])
def test_qa6_demonstrative_explain_without_target_asks_back(real_catalog, first):
    api = Api(real_catalog)
    if first:
        api.say(first)
    r = api.say("거기 어디야?")
    assert r["answer"] == CLARIFY_ANSWER
    assert r["places"] == [] and r["center"] is None


def test_qa6_demonstrative_near_first_message_still_recommends(real_catalog):
    api = Api(real_catalog)
    r = api.say("거기 근처 카페 있어?")
    assert is_cafe(real_catalog, r)


def test_qa7_earlier_list_reference(real_catalog):
    """QA-7: 직전 목록(관광지)에 없으면 그 전 추천 목록(맛집)에서 '아까 그 식당'을 찾는다."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    r1 = api.say("명동 맛집 추천해줘")
    api.say("광화문 근처 관광지")
    r = api.say("아까 그 식당 몇 시에 열어?")
    assert_place_info(r)
    label = api.history()[-1]["center"]["label"]
    assert label in [p["title"] for p in r1["places"]]


# ---------------------------------------------------------------- 2글자 장소명 (팀원1 개선)

def test_short_title_common_word_not_center(real_catalog):
    """'기후'(장소명)가 일반 단어로 쓰이면 기준점이 아님."""
    api = Api(real_catalog)
    r = api.say("기후 변화 걱정 없는 실내 관광지 추천해줘")
    assert r["center"] is None or r["center"]["label"] != "기후"


def test_short_title_used_as_place_is_center(real_catalog):
    api = Api(real_catalog)
    r = api.say("기후 근처 카페")
    assert r["center"]["label"] == "기후" and r["center"]["source"] == "place"


# ---------------------------------------------------------------- 구 전체·관광 세부 주제 (팀원1 51b8c0d)

def gu_of(catalog, body):
    return {catalog[p["id"]].gu for p in body["places"]}


@pytest.mark.parametrize("message", ["강서구에 산책할만한 곳 알려줘", "강서구 공원 추천해줘"])
def test_gu_wide_nature_topic_first(real_catalog, message):
    """구 기준점이면 구 전체에서 고르고(1.5km 제한 없음), 산책·공원에 맞는 곳이 1번."""
    api = Api(real_catalog)
    r = api.say(message)
    assert r["center"]["source"] == "gu" and r["center"]["label"] == "강서구"
    assert r["places"] and gu_of(real_catalog, r) == {"강서구"}
    first = r["places"][0]
    assert matches_topic(first["category"], first["title"], "nature"), first
    # 반경이 아니라 구 전체 → 장소 줄에 '기준점에서 조금 멂'·도보 표시 없음, 구 안이라는 규칙
    prompt = api.last_prompt()
    assert "/ 기준점에서 조금 멂" not in prompt and "/ 도보 " not in prompt
    assert "강서구 안에서 고른 곳" in prompt


def assert_gu_no_distance(body, gu):
    """QA-8 최종: 기준점이 구(첫 턴이든 이어받은 턴이든)면 source=gu, 거리·도보 null."""
    assert body["center"]["source"] == "gu" and body["center"]["label"] == gu, body["center"]
    assert body["places"], body["answer"]
    for p in body["places"]:
        assert p["distance_m"] is None and p["walk_min"] is None, p


def far_from_center(body):
    c = body["center"]
    return any(haversine_m(c["lat"], c["lng"], p["lat"], p["lng"]) > 1500 for p in body["places"])


def test_gu_wide_may_exceed_radius(real_catalog):
    """구 전체에서 고르므로 구 중심에서 1.5km 넘는 곳도 나옴(응답의 거리는 null이라 좌표로 직접 잼)."""
    api = Api(real_catalog)
    r = api.say("종로 관광지")
    assert gu_of(real_catalog, r) == {"종로구"}
    assert_gu_no_distance(r, "종로구")
    far_seen = far_from_center(r)
    for _ in range(3):  # 구 전체라 '다른 데 더'를 해도 같은 구 안에서 계속 나옴
        r = api.say("다른 데 더 추천해줘")
        if not r["places"]:
            break
        assert gu_of(real_catalog, r) <= {"종로구"}
        assert_gu_no_distance(r, "종로구")
        far_seen = far_seen or far_from_center(r)
    assert far_seen


@pytest.mark.parametrize("follow", ["다른 데 더 추천해줘", "맛집은?"])
def test_gu_carried_turn_is_gu_without_distance(real_catalog, follow):
    """QA-8(2fee772): 구 결과 뒤 이어받은 턴도 center.source=gu, 거리·도보 null (예전엔 history + 거리)."""
    api = Api(real_catalog)
    assert_gu_no_distance(api.say("강서구 공원 추천해줘"), "강서구")
    r = api.say(follow)
    assert_gu_no_distance(r, "강서구")
    assert gu_of(real_catalog, r) == {"강서구"}


def test_gu_carried_twice_stays_gu(real_catalog):
    """두 번 이어받아도(구 관광지 → 맛집은? → 다른 데 더) 계속 gu."""
    api = Api(real_catalog)
    api.say("마포구 관광지 추천해줘")
    assert_gu_no_distance(api.say("맛집은?"), "마포구")
    assert_gu_no_distance(api.say("다른 데 더 추천해줘"), "마포구")


@pytest.mark.parametrize("turns", [["강서구 카페 추천해줘"], ["강서구 공원 추천해줘", "카페는?"]])
def test_qa9_gu_with_no_match_still_no_distance(real_catalog, turns):
    """QA-9(c9cace1): 강서구엔 카페가 0곳(카탈로그 카페 14곳) → 다른 구 카페로 채워도 source gu·거리 null
    (예전엔 용산구 카페가 12838m·192분으로 나와 화면에 '🚶 강서구에서 약 192분'이 보였음)."""
    api = Api(real_catalog)
    for t in turns:
        r = api.say(t)
    assert_gu_no_distance(r, "강서구")
    assert len(r["places"]) >= 3 and "강서구" not in gu_of(real_catalog, r)


@pytest.mark.parametrize("turns", [["강서구 카페 추천해줘"], ["강서구 공원 추천해줘", "카페는?"]])
def test_qa9_gu_empty_notice(real_catalog, turns):
    """구 안에 0곳 → 답 첫머리에 '강서구 안에는 카페 정보가 없어서, 가까운 다른 구의 카페를 보여 드려요.'
    LLM 다운(템플릿)·LLM이 다른 구를 말 안 함 두 경우 모두."""
    notice = GU_EMPTY_NOTICE.format(gu="강서구", what="카페", what_obj="카페를")
    for llm in (FakeLLM(fail=True), FakeLLM("가짜 답변이에요.")):
        api = Api(real_catalog, llm=llm)
        for t in turns:
            r = api.say(t)
        assert r["answer"].startswith(notice), r["answer"]
        assert "근처" not in r["answer"]


def test_qa9_notice_skipped_when_llm_names_other_gu(real_catalog):
    """LLM 답이 다른 구 이름을 이미 말하고 '없다'고 하면 안내를 덧붙이지 않음."""
    api = Api(real_catalog, llm=FakeLLM("강서구에는 카페 정보가 없어서 용산구와 종로구 카페를 골랐어요."))
    r = api.say("강서구 카페 추천해줘")
    assert r["answer"] == "강서구에는 카페 정보가 없어서 용산구와 종로구 카페를 골랐어요."


def test_qa9_gu_empty_prompt_rule(real_catalog):
    """프롬프트: 구 안에 없다는 규칙 + 장소마다 '구: 용산구 (강서구 밖의 다른 구)'."""
    api = Api(real_catalog)
    api.say("강서구 카페 추천해줘")
    prompt = api.last_prompt()
    assert "'강서구' 안에는 맞는 카페 정보가 없어서" in prompt
    assert "(강서구 밖의 다른 구)" in prompt and "/ 도보 " not in prompt


def test_qa9_gu_fill_notice(real_catalog):
    """금천구 음식점은 1곳 → 다른 구(영등포구·관악구)로 3곳 채움 + 안내, 거리 null, 금천구 장소가 1번."""
    api = Api(real_catalog, llm=FakeLLM("가짜 답변이에요."))
    r = api.say("금천구 맛집 추천해줘")
    assert_gu_no_distance(r, "금천구")
    gus = [real_catalog[p["id"]].gu for p in r["places"]]
    assert gus[0] == "금천구" and gus.count("금천구") == 1 and len(gus) == 3
    others = "·".join(dict.fromkeys(g for g in gus if g != "금천구"))
    assert r["answer"].startswith(GU_FILL_NOTICE.format(gu="금천구", n=1, others=others)), r["answer"]


def test_qa9_gu_more_notices(real_catalog):
    """'다른 데 더': 0곳 → GU_EMPTY_MORE_NOTICE, 금천구(남은 0곳) → 음식점 EMPTY_MORE."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    api.say("강서구 카페 추천해줘")
    r = api.say("다른 데 더 추천해줘")
    assert_gu_no_distance(r, "강서구")
    assert r["answer"].startswith(GU_EMPTY_MORE_NOTICE.format(gu="강서구", what="카페", what_obj="카페를")), r["answer"]
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    api.say("금천구 맛집 추천해줘")
    r = api.say("다른 데 더 추천해줘")
    assert_gu_no_distance(r, "금천구")
    assert r["answer"].startswith(GU_EMPTY_MORE_NOTICE.format(gu="금천구", what="음식점", what_obj="음식점을")), r["answer"]
    assert GU_FILL_MORE_NOTICE  # 1~2곳 남은 '다른 데 더' 문구는 백엔드 단위 테스트가 확인


def test_qa9_enough_in_gu_has_no_notice(real_catalog):
    """강남구 맛집은 구 안에 충분 → 안내 없음, 모두 강남구."""
    for llm in (FakeLLM(fail=True), FakeLLM("가짜 답변이에요.")):
        api = Api(real_catalog, llm=llm)
        r = api.say("강남구 맛집 추천해줘")
        assert_gu_no_distance(r, "강남구")
        assert gu_of(real_catalog, r) == {"강남구"}
        assert "다른 구" not in r["answer"] and "정보가 없어서" not in r["answer"], r["answer"]


@pytest.mark.parametrize("message, source", [
    ("명동 맛집 추천해줘", "area"),
    ("광화문 근처 맛집 추천해줘", "place"),
])
def test_non_gu_keeps_int_distance(real_catalog, message, source):
    """area/place 기준점은 거리·도보 int 그대로(QA-8은 gu만 바꿈)."""
    api = Api(real_catalog)
    r = api.say(message)
    assert r["center"]["source"] == source
    assert r["places"]
    for p in r["places"]:
        assert isinstance(p["distance_m"], int) and isinstance(p["walk_min"], int), p


def test_gps_keeps_int_distance(real_catalog):
    api = Api(real_catalog)
    r = api.say("근처 맛집 추천해줘", location={"lat": 37.5665, "lng": 126.9780})
    assert r["center"]["source"] == "gps"
    assert r["places"]
    for p in r["places"]:
        assert isinstance(p["distance_m"], int) and isinstance(p["walk_min"], int), p


@pytest.mark.parametrize("follow", ["카페는?", "다른 데 더 추천해줘"])
def test_area_carried_turn_is_history_with_distance(real_catalog, follow):
    """명동(area)을 이어받은 턴은 source=history, 거리 int 유지 (gu 규칙과 섞이지 않음)."""
    api = Api(real_catalog)
    api.say("명동 맛집 추천해줘")
    r = api.say(follow)
    assert r["center"]["source"] == "history" and r["center"]["label"] == "명동"
    assert r["places"]
    for p in r["places"]:
        assert isinstance(p["distance_m"], int) and isinstance(p["walk_min"], int), p


def test_gu_wide_more_has_no_far_notice(real_catalog):
    """구 기준점의 '다른 데 더'는 결과가 모두 1.5km 밖이어도 '근처(1.5km 안)에는 없어서' 안내를 붙이지 않음."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    api.say("종로 관광지")
    for _ in range(4):
        r = api.say("다른 데 더 추천해줘")
        if not r["places"]:
            break
        assert "1.5km 안" not in r["answer"]
        assert_gu_no_distance(r, "종로구")


def test_topic_missing_notice(real_catalog):
    """'금천구 산책할 곳' — 맞는 곳이 없으면 솔직히 안내 (LLM 다운 템플릿)."""
    api = Api(real_catalog, llm=FakeLLM(fail=True))
    r = api.say("금천구 산책할 곳")
    assert r["places"]
    assert not any(matches_topic(p["category"], p["title"], "nature") for p in r["places"])
    assert r["answer"].startswith(TOPIC_MISSING_NOTICE.format(where="금천구에서 ", topic="산책·자연"))


def test_topic_missing_notice_added_when_llm_omits(real_catalog):
    api = Api(real_catalog, llm=FakeLLM("금천구 관광지를 골라봤어요."))
    r = api.say("금천구 산책할 곳")
    assert r["answer"] == TOPIC_MISSING_NOTICE.format(where="금천구에서 ", topic="산책·자연") + " 금천구 관광지를 골라봤어요."


def test_hangang_food_is_food_only(real_catalog):
    """'한강 근처 맛집'의 한강은 산책 주제가 아님 → 음식점만."""
    api = Api(real_catalog)
    r = api.say("한강 근처 맛집")
    assert r["places"] and all(p["kind"] == "food" for p in r["places"])


def test_topic_carried_to_more(real_catalog):
    """'강서구 공원' → '다른 데 더': 구·관광·산책 주제 유지, 이전과 안 겹침, 주제 맞는 곳이 앞."""
    api = Api(real_catalog)
    r1 = api.say("강서구 공원 추천해줘")
    r2 = api.say("다른 데 더 추천해줘")
    assert r2["places"], r2["answer"]
    assert_gu_no_distance(r2, "강서구")
    assert all(p["kind"] == "tour" for p in r2["places"])
    assert not set(ids(r2)) & set(ids(r1))
    # 주제를 이어받음: 맞는 곳이 남아 있으면 '질문 주제는', 다 썼으면 '딱 맞는 곳이 없다' 규칙 — 어느 쪽이든 산책·자연
    assert "'산책·자연'" in api.last_prompt()


def test_topic_carried_to_more_in_gu_wide_prompt_has_no_far_rule(real_catalog):
    """b689e90: 구 결과 프롬프트에는 '기준점에서 조금 멂' 규칙 자체가 없음."""
    api = Api(real_catalog)
    api.say("종로 관광지")
    assert "기준점에서 조금 멂" not in api.last_prompt()


def test_gunggeum_does_not_trigger_history_topic(real_catalog):
    api = Api(real_catalog)
    r = api.say("궁금한 게 있는데 종로 관광지 추천해줘")
    assert r["center"]["label"] == "종로구" and all(p["kind"] == "tour" for p in r["places"])
    assert "질문 주제는" not in api.last_prompt()  # '궁금'의 '궁'으로 역사 주제가 잡히지 않음


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
