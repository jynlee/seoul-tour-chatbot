"""B8(장소 정보 질문) + B9(멀티턴) 회귀 테스트. 실제 카탈로그(574곳) + FakeSearcher/FakeLLM."""
import dataclasses

import pytest

from app.catalog import load_catalog
from app.chat import ChatService, Deps
from app.history import InMemoryHistoryRepo
from app.llm import CLARIFY_ANSWER, ORDINAL_OUT_OF_RANGE, info_template_answer
from app.schemas import ChatRequest
from tests.conftest import FakeEmbedder, FakeLLM, FakeSearcher

CAFE = "A05020900"


@pytest.fixture(scope="module")
def real_catalog(tmp_path_factory):
    catalog = load_catalog("data/seoul_tour.json", tmp_path_factory.mktemp("e") / "none.json")
    by_title = {p.title: p for p in catalog.values()}
    # B8용 상세 정보: 고려삼계탕은 주차 정보만 없음, 개성만두 궁은 주차 '불가능'
    gs = by_title["고려삼계탕"]
    catalog[gs.id] = dataclasses.replace(gs, tel="02-752-9376", detail={"hours": "10:00~22:00", "menu": "삼계탕"})
    gm = by_title["개성만두 궁"]
    catalog[gm.id] = dataclasses.replace(gm, tel="02-733-9240", detail={"parking": "불가능", "menu": "고기만두전골"})
    return catalog


class Session:
    def __init__(self, catalog, llm=None):
        self.catalog = catalog
        self.deps = Deps(catalog=catalog, embedder=FakeEmbedder(), searcher=FakeSearcher(catalog),
                         llm=llm or FakeLLM("가짜 답변이에요."), history=InMemoryHistoryRepo())
        self.svc = ChatService(self.deps)
        self.sid = None

    def say(self, message, selected=None, location=None):
        res = self.svc.handle(ChatRequest(session_id=self.sid, message=message, selected_place_id=selected,
                                          location=location))
        self.sid = res.session_id
        return res

    def title_id(self, title):
        return next(p.id for p in self.catalog.values() if p.title == title)


def _titles(res):
    return [p.title for p in res.places]


# ---------------- 리드 재현 세션 1 ----------------

def test_session1_myeongdong(real_catalog):
    s = Session(real_catalog)
    r1 = s.say("명동 맛집 추천해줘")
    assert r1.center.label == "명동" and r1.places and all(p.kind == "food" for p in r1.places)

    r2 = s.say("카페는?")
    assert r2.center.label == "명동"
    assert r2.places and all(real_catalog[p.id].cat3 == CAFE for p in r2.places)

    # 직전 카테고리(카페)·지역(명동)을 이어받고, 이미 보여 준 곳은 뺀다
    r3 = s.say("다른 데 더 추천해줘")
    assert r3.center.label == "명동"
    assert r3.places and all(real_catalog[p.id].cat3 == CAFE for p in r3.places)
    assert not set(_titles(r3)) & set(_titles(r2))

    # 순서 지칭 → 장소 정보(재검색·핀 교체 없음)
    llm_calls = len(s.deps.llm.prompts)
    r4 = s.say("두 번째 거기 어디야?")
    assert r4.places == [] and r4.center is None
    assert r3.places[1].title in s.deps.llm.prompts[llm_calls]
    # 기록의 마지막 추천은 여전히 r3 (새로고침해도 핀 유지)
    assert [p.id for p in s.deps.history.last_assistant(s.sid).places] == [p.id for p in r3.places]


# ---------------- 리드 재현 세션 2 ----------------

def test_session2_gangnam(real_catalog):
    s = Session(real_catalog)
    r1 = s.say("강남 관광지 알려줘")
    assert r1.center.source == "gu" and r1.center.label == "강남구"  # 같은 이름의 장소 '강남'보다 구가 우선
    assert "강남" not in _titles(r1)
    assert all(p.kind == "tour" for p in r1.places)

    n = len(s.deps.llm.prompts)
    r2 = s.say("아까 첫 번째 거 다시 알려줘")
    assert r2.places == [] and r2.center is None
    assert r1.places[0].title in s.deps.llm.prompts[n]

    r3 = s.say("거기서 가까운 맛집은?")
    assert r3.center.label == r1.places[0].title  # 방금 설명한 1번 장소 기준
    assert r3.places and all(p.kind == "food" for p in r3.places)


# ---------------- B8 장소 정보 질문 ----------------

def test_info_by_name_prefers_recent_list(real_catalog):
    s = Session(real_catalog)
    s.say("명동 맛집 추천해줘")
    n = len(s.deps.llm.prompts)
    r = s.say("고려삼계탕 몇 시에 열어?")
    assert r.places == [] and r.center is None
    prompt = s.deps.llm.prompts[n]
    assert "고려삼계탕" in prompt and "10:00~22:00" in prompt


def test_info_missing_field_no_llm(real_catalog):
    s = Session(real_catalog)
    s.say("명동 맛집 추천해줘")
    n = len(s.deps.llm.prompts)
    r = s.say("고려삼계탕 주차 가능해?")
    assert r.answer == "고려삼계탕 — 주차 정보는 없어요. 전화(02-752-9376)로 확인해 보세요."
    assert len(s.deps.llm.prompts) == n  # 정보가 없으면 LLM을 부르지 않음(지어내기 방지)
    assert r.places == []


def test_info_demonstrative_selected(real_catalog):
    s = Session(real_catalog, llm=FakeLLM(fail=True))
    r1 = s.say("명동 맛집 추천해줘")
    gm = s.title_id("개성만두 궁")
    assert gm in [p.id for p in r1.places]
    r = s.say("거기 주차 돼?", selected=gm)
    assert r.answer == "개성만두 궁 — 주차: 불가능."
    assert r.places == [] and r.center is None


def test_info_demonstrative_first_place(real_catalog):
    s = Session(real_catalog, llm=FakeLLM(fail=True))
    r1 = s.say("명동 맛집 추천해줘")
    r = s.say("그곳 전화번호 알려줘")
    first = real_catalog[r1.places[0].id]
    assert r.answer.startswith(first.title)


def test_info_llm_down_uses_detail(real_catalog):
    s = Session(real_catalog, llm=FakeLLM(fail=True))
    s.say("명동 맛집 추천해줘")
    r = s.say("고려삼계탕 메뉴 뭐가 맛있어?")
    assert r.answer == "고려삼계탕 — 메뉴: 삼계탕."


def test_info_no_target_asks_back(real_catalog):
    s = Session(real_catalog)
    r = s.say("주차 가능해?")
    assert r.answer == CLARIFY_ANSWER
    assert r.places == [] and r.center is None


def test_demonstrative_near_cafe_still_recommends(real_catalog):
    s = Session(real_catalog)
    s.say("명동 맛집 추천해줘")
    gm = s.title_id("개성만두 궁")
    r = s.say("거기 근처 카페 있어?", selected=gm)
    assert r.center.label == "개성만두 궁"
    assert r.places and all(real_catalog[p.id].cat3 == CAFE for p in r.places)


def test_partial_name_reference(real_catalog):
    s = Session(real_catalog, llm=FakeLLM(fail=True))
    s.say("명동 맛집 추천해줘")
    r = s.say("그 삼계탕집 몇 시에 열어?")
    assert r.answer == "고려삼계탕 — 이용 시간: 10:00~22:00."


def test_focus_after_info_then_near(real_catalog):
    s = Session(real_catalog)
    s.say("명동 맛집 추천해줘")
    s.say("고려삼계탕 주차 가능해?")
    r = s.say("거기 근처 카페 있어?")
    assert r.center.label == "고려삼계탕"


def test_info_template_general():
    from tests.conftest import SMALL_PLACES

    p = SMALL_PLACES[2]  # 가회동성당
    assert info_template_answer(p, []) == "가회동성당: 역사관광지, 주소 서울특별시 종로구 북촌로 57 (가회동), 전화 02-763-1570."


def test_short_title_common_word_not_center(real_catalog):
    # 장소 '기후'(성수 일식집)가 '기후 변화'의 기후로 기준점이 되면 안 됨
    s = Session(real_catalog)
    r = s.say("기후 변화 걱정 없는 실내 관광지 추천해줘")
    assert r.center is None
    r = s.say("기후 맛집 근처 카페")
    assert r.center.label == "기후"


# ---------------- QA-4~7 ----------------

def test_qa4_palace_in_title(real_catalog):
    s = Session(real_catalog, llm=FakeLLM(fail=True))
    r1 = s.say("종로 관광지")
    palace = next(p.title for p in r1.places if "궁" in p.title)
    r = s.say("아까 그 궁 주차돼?")
    assert r.answer.startswith(palace)


def test_qa5_ordinal_out_of_range_asks_back(real_catalog):
    s = Session(real_catalog)
    r1 = s.say("성수 카페")
    n = len(r1.places)
    r = s.say(f"{n + 1}번째 거 어디야?")
    assert r.places == [] and r.center is None
    assert r.answer == ORDINAL_OUT_OF_RANGE.format(n=n)


def test_qa6_demonstrative_without_context_asks_back(real_catalog):
    s = Session(real_catalog)
    assert s.say("주차 가능해?").answer == CLARIFY_ANSWER
    r = s.say("거기 어디야?")
    assert r.answer == CLARIFY_ANSWER and r.places == [] and r.center is None
    r = Session(real_catalog).say("거기 어디야?")
    assert r.answer == CLARIFY_ANSWER and r.places == []


def test_qa7_earlier_list_reference(real_catalog):
    s = Session(real_catalog, llm=FakeLLM(fail=True))
    r1 = s.say("명동 맛집 추천해줘")
    s.say("광화문 근처 관광지")
    r = s.say("아까 그 식당 몇 시에 열어?")
    # 이전 맛집 목록 중 한 곳(이름에 '식당'이 든 곳이 있으면 그곳)에 대한 답
    assert any(r.answer.startswith(f"{p.title} —") for p in r1.places)
    assert r.places == []


# ---------------- 구 기준점 + 산책·공원 의도 (리드 재현) ----------------

def test_gangseo_walk_and_park(real_catalog):
    for q in ("강서구에 산책할만한 곳 알려줘", "강서구 공원 추천해줘"):
        r = Session(real_catalog).say(q)
        assert r.center.label == "강서구", q
        assert r.places[0].title == "강서습지생태공원", q
        assert all(real_catalog[p.id].gu == "강서구" for p in r.places), q
        assert all(p.distance_m is None and p.walk_min is None for p in r.places), q  # QA-8


def test_topic_missing_says_so(real_catalog):
    # 금천구에는 자연·공원 관광지가 없음 → 솔직히 말하고 비슷한 관광지
    s = Session(real_catalog, llm=FakeLLM(fail=True))
    r = s.say("금천구 산책할 곳 추천해줘")
    assert r.places and all(p.kind == "tour" for p in r.places)
    assert r.answer.startswith("금천구에서 산책·자연에 딱 맞는 곳은 못 찾아서 비슷한 관광지를 골랐어요.")
    s2 = Session(real_catalog)
    s2.say("금천구 산책할 곳 추천해줘")
    assert "산책·자연" in s2.deps.llm.prompts[-1]


def test_topic_carried_to_more_request(real_catalog):
    s = Session(real_catalog)
    r1 = s.say("강서구 공원 추천해줘")
    r2 = s.say("다른 데 더 추천해줘")
    assert (r2.center.source, r2.center.label) == ("gu", "강서구")
    assert all(p.distance_m is None and p.walk_min is None for p in r2.places)
    assert not set(_titles(r2)) & set(_titles(r1))
    assert "산책·자연" in s.deps.llm.prompts[-1]  # 직전 주제를 이어받음


# ---------------- 괄호 이름 + 되묻기 뒤 이름만 답하기 (사용자 재현) ----------------

def _seokpajeong_session(real_catalog):
    by_title = {p.title: p for p in real_catalog.values()}
    sp = by_title["대원군별장(석파정)"]
    catalog = dict(real_catalog)
    catalog[sp.id] = dataclasses.replace(sp, tel="02-395-0100", detail={"contact": "02-395-0100"})  # 요금 정보 없음
    s = Session(catalog)
    s.deps.searcher = FakeSearcher(catalog, scores={by_title["바라캇 서울"].id: 3.0, sp.id: 2.0})
    return s, catalog[sp.id]


def test_parenthesized_title_info_question(real_catalog):
    s, sp = _seokpajeong_session(real_catalog)
    r1 = s.say("종로 관광지 추천해줘")
    assert "대원군별장(석파정)" in _titles(r1)
    r2 = s.say("석파정 무료 입장이야?")
    assert r2.answer == info_template_answer(sp, ["fee"])  # 요금 정보 없음 → 지어내지 않고 문의처 안내
    assert "02-395-0100" in r2.answer
    assert r2.places == [] and r2.center is None


def test_name_only_answer_after_clarify_keeps_question(real_catalog):
    s, sp = _seokpajeong_session(real_catalog)
    s.say("종로 관광지 추천해줘")
    r2 = s.say("무료 입장이야?")
    assert r2.answer == CLARIFY_ANSWER
    r3 = s.say("대원군별장")
    assert r3.answer == info_template_answer(sp, ["fee"])  # 앞 질문(요금)을 이어받아 답함
    assert r3.places == [] and r3.center is None


def test_name_only_after_clarify_explain(real_catalog):
    s, sp = _seokpajeong_session(real_catalog)
    r2 = s.say("거기 어디야?")
    assert r2.answer == CLARIFY_ANSWER
    calls = len(s.deps.llm.prompts)
    r3 = s.say("석파정")
    assert r3.places == [] and r3.center is None  # 추천이 아니라 장소 설명
    assert sp.title in s.deps.llm.prompts[calls]


# ---------------- QA-9: 구 안에 맞는 곳이 0곳·1~2곳일 때 ----------------

def _assert_gu_no_distance(r, gu):
    assert (r.center.source, r.center.label) == ("gu", gu)
    assert r.places
    assert all(p.distance_m is None and p.walk_min is None for p in r.places)


@pytest.mark.parametrize("turns", [["강서구 카페 추천해줘"], ["강서구 공원 추천해줘", "카페는?"]])
def test_qa9_gu_without_match_shows_other_gu_honestly(real_catalog, turns):
    # 카탈로그 카페 14곳 중 강서구는 0곳 → 가까운 다른 구 카페, 거리 null, 첫머리에 솔직히
    s = Session(real_catalog, llm=FakeLLM(fail=True))
    for t in turns:
        r = s.say(t)
    _assert_gu_no_distance(r, "강서구")
    assert all(real_catalog[p.id].cat3 == CAFE and real_catalog[p.id].gu != "강서구" for p in r.places)
    assert r.answer.startswith("강서구 안에는 카페 정보가 없어서, 가까운 다른 구의 카페를 보여 드려요.")
    assert "근처" not in r.answer and "km" not in r.answer


def test_qa9_prompt_has_each_place_gu_and_notice_added(real_catalog):
    s = Session(real_catalog)  # FakeLLM 답에는 안내가 없음 → 앞에 붙임
    r = s.say("강서구 카페 추천해줘")
    prompt = s.deps.llm.prompts[-1]
    for p in r.places:
        assert f"구: {real_catalog[p.id].gu}" in prompt
    assert "'강서구' 안에는 맞는 카페 정보가 없어서" in prompt  # LLM에게 솔직히 말하라는 규칙
    assert r.answer == "강서구 안에는 카페 정보가 없어서, 가까운 다른 구의 카페를 보여 드려요. 가짜 답변이에요."


def test_qa9_notice_not_duplicated_when_llm_says_it(real_catalog):
    said = "강서구에는 카페가 없어서 다른 구인 용산구 카페를 골랐어요."
    r = Session(real_catalog, llm=FakeLLM(said)).say("강서구 카페 추천해줘")
    assert r.answer == said


def test_qa9_partial_fill_names_other_gu(real_catalog):
    # 금천구 음식점은 1곳 → 다른 구 2곳으로 채움. 거리 null, 채운 곳이 다른 구라는 걸 답에서 알 수 있게
    s = Session(real_catalog)
    r = s.say("금천구 맛집 추천해줘")
    _assert_gu_no_distance(r, "금천구")
    gus = [real_catalog[p.id].gu for p in r.places]
    assert gus[0] == "금천구" and len(r.places) == 3 and all(g != "금천구" for g in gus[1:])
    others = "·".join(dict.fromkeys(gus[1:]))
    assert r.answer.startswith(f"금천구 안에는 1곳뿐이라 가까운 다른 구({others})의 곳도 함께 골랐어요.")
    assert "구: 금천구" in s.deps.llm.prompts[-1]

    r2 = Session(real_catalog, llm=FakeLLM(f"금천구 맛집과 함께 {gus[1]}의 맛집도 골랐어요.")).say("금천구 맛집 추천해줘")
    assert r2.answer == f"금천구 맛집과 함께 {gus[1]}의 맛집도 골랐어요."  # 다른 구 이름을 말했으면 안 붙임


def test_gu_with_enough_places_has_no_notice(real_catalog):
    r = Session(real_catalog).say("강남구 맛집 추천해줘")
    _assert_gu_no_distance(r, "강남구")
    assert all(real_catalog[p.id].gu == "강남구" for p in r.places)
    assert r.answer == "가짜 답변이에요."
