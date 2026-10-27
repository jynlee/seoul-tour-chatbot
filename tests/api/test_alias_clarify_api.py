"""QA: 2b4a42a — 괄호가 든 장소 이름(괄호 뺀 이름·괄호 안 이름) 인식, 되묻기 뒤 이름만 답하면 앞 질문 이어받기.

POST /api/chat·GET /api/history (가짜 의존성 + 실제 카탈로그 574곳, 상세 정보 없음 → 정보 질문은 템플릿 답).
"""
import pytest

from app.llm import CLARIFY_ANSWER
from tests.api.test_multiturn_api import Api, assert_place_info, real_catalog  # noqa: F401 (fixture)

SEOKPA = "대원군별장(석파정)"
GILSANG = "길상사(서울)"


def info_label(api):
    """정보 질문 응답은 center=null → 설명한 장소는 기록의 center.label로 확인."""
    return api.history()[-1]["center"]["label"]


# ---------------------------------------------------------------- 괄호 이름 → 장소 정보 질문

@pytest.mark.parametrize("message", ["석파정 무료 입장이야?", "대원군별장 무료 입장이야?", "대원군별장(석파정) 무료 입장이야?"])
def test_alias_info_first_turn(real_catalog, message):
    """괄호 안 이름·괄호 뺀 이름·원래 제목 모두 같은 장소. 요금 정보가 없으니 지어내지 않고 템플릿."""
    api = Api(real_catalog)
    r = api.say(message)
    assert_place_info(r)
    assert info_label(api) == SEOKPA
    assert r["answer"].startswith(f"{SEOKPA} — 요금 정보는 없어요.")
    assert api.llm.prompts == []  # 물어본 정보가 하나도 없으면 LLM 생략


def test_alias_info_after_list(real_catalog):
    """backend-2 예시: '종로 관광지' → '석파정 무료 입장이야?' (직전 목록에 없어도 카탈로그에서 찾음)."""
    api = Api(real_catalog)
    api.say("종로 관광지 추천해줘")
    r = api.say("석파정 무료 입장이야?")
    assert_place_info(r)
    assert info_label(api) == SEOKPA and "요금 정보는 없어요" in r["answer"]


def test_alias_in_last_list_wins(real_catalog):
    """직전 목록에 괄호 제목이 있으면 괄호 안 이름으로 지칭 가능 (목록 우선 경로)."""
    api = Api(real_catalog)
    r1 = api.say("부암동 관광지")
    assert r1["places"][0]["title"] == SEOKPA
    r = api.say("석파정 몇 시에 열어?")
    assert_place_info(r)
    assert info_label(api) == SEOKPA


@pytest.mark.parametrize("message, title", [
    ("길상사 어디야?", GILSANG),
    ("세계태권도본부 주차 돼?", "국기원(세계태권도본부)"),
    ("kspo dome 몇 시에 열어?", "올림픽체조경기장(KSPO DOME)"),  # 영문 대소문자 무시
    ("이씨레물리노공원 주차 돼?", "구로근린공원(이씨레물리노공원)"),
    ("간송미술관 쉬는 날 언제야?", "간송미술관(서울 보화각)"),
])
def test_alias_info_various(real_catalog, message, title):
    api = Api(real_catalog)
    r = api.say(message)
    assert_place_info(r)
    assert info_label(api) == title


# ---------------------------------------------------------------- 괄호 이름 → 기준점

@pytest.mark.parametrize("message, title", [
    ("석파정 근처 맛집", SEOKPA),
    ("국기원 근처 카페", "국기원(세계태권도본부)"),
    ("KSPO DOME 근처 맛집", "올림픽체조경기장(KSPO DOME)"),
    ("남산공원 근처 카페", "남산공원(서울)"),  # 회귀 주의점: 전에는 지역 남산
])
def test_alias_as_center(real_catalog, message, title):
    api = Api(real_catalog)
    r = api.say(message)
    assert r["center"]["source"] == "place" and r["center"]["label"] == title  # label은 원래 제목 그대로
    assert r["places"] and title not in [p["title"] for p in r["places"]]  # 기준점 장소 자체는 결과에서 빠짐


def test_alias_name_only_without_clarify_recommends_near(real_catalog):
    """되묻기 상황이 아니면 이름만 말해도 기존처럼 그 장소 근처 추천."""
    api = Api(real_catalog)
    r = api.say("석파정")
    assert r["center"]["source"] == "place" and r["center"]["label"] == SEOKPA
    assert r["places"]


# ---------------------------------------------------------------- 이름으로 치지 않는 괄호 안 말·회귀

def test_namsan_food_still_area(real_catalog):
    r = Api(real_catalog).say("남산 맛집")
    assert r["center"]["source"] == "area" and r["center"]["label"] == "남산"


@pytest.mark.parametrize("message", ["서울 관광지 추천해줘", "실내 관광지 추천해줘", "실외 수영장 추천해줘"])
def test_not_name_words_are_not_place(real_catalog, message):
    """'서울'·'실내'·'실외'는 괄호 안에 있어도 장소 이름이 아님."""
    r = Api(real_catalog).say(message)
    assert r["center"] is None or r["center"]["source"] != "place", r["center"]


@pytest.mark.parametrize("message", ["강남코엑스점 근처 맛집", "부마도위박영효가옥 근처 카페"])
def test_branch_and_old_name_inner_are_not_alias(real_catalog, message):
    """'…점'(지점)·'구 ○○'(옛 이름)은 별명이 아님 → 그 이름으로는 해당 장소가 기준점이 되지 않음."""
    r = Api(real_catalog).say(message)
    assert r["center"] is None or r["center"]["label"] not in ("세븐럭카지노(강남코엑스점)", "관훈동 민씨 가옥 (구 부마도위박영효가옥)")


def test_branch_base_name_is_alias(real_catalog):
    r = Api(real_catalog).say("세븐럭카지노 근처 맛집")
    assert r["center"]["label"] == "세븐럭카지노(강남코엑스점)"


def test_two_letter_alias_common_word_not_place(real_catalog):
    """'공기(Gongi)'의 괄호 뺀 이름 '공기'는 2글자 → 일반 단어로 쓰이면 장소 아님."""
    r = Api(real_catalog).say("공기 좋은 산책 코스 추천해줘")
    assert r["center"] is None or r["center"]["label"] != "공기(Gongi)", r["center"]


def test_two_letter_alias_used_as_place(real_catalog):
    r = Api(real_catalog).say("공기 근처 카페")
    assert r["center"]["source"] == "place" and r["center"]["label"] == "공기(Gongi)"


def test_hangang_food_regression(real_catalog):
    r = Api(real_catalog).say("한강 근처 맛집")
    assert r["places"] and all(p["kind"] == "food" for p in r["places"])


# ---------------------------------------------------------------- 되묻기 뒤 이름만 답하기

def test_clarify_then_name_carries_field(real_catalog):
    """'무료 입장이야?' → 되묻기 → '대원군별장' → 요금 답 (backend-2 예시)."""
    api = Api(real_catalog)
    r1 = api.say("무료 입장이야?")
    assert r1["answer"] == CLARIFY_ANSWER
    r2 = api.say("대원군별장")
    assert_place_info(r2)
    assert info_label(api) == SEOKPA
    assert r2["answer"].startswith(f"{SEOKPA} — 요금 정보는 없어요.")


def test_clarify_then_name_carries_explain(real_catalog):
    """'거기 어디야?' → 되묻기 → '길상사' → 길상사 설명(LLM 프롬프트에 장소와 앞 질문)."""
    api = Api(real_catalog)
    assert api.say("거기 어디야?")["answer"] == CLARIFY_ANSWER
    r = api.say("길상사")
    assert_place_info(r)
    assert info_label(api) == GILSANG
    prompt = api.last_prompt()
    assert f"이름: {GILSANG}" in prompt and "거기 어디야?" in prompt


def test_clarify_then_name_llm_prompt_has_previous_question(real_catalog):
    """정보가 있는 장소면 LLM으로 → 프롬프트 질문에 앞 질문이 이어 붙음 (개성만두 궁: 주차 '불가능')."""
    api = Api(real_catalog)
    assert api.say("주차 가능해?")["answer"] == CLARIFY_ANSWER
    r = api.say("개성만두 궁")
    assert_place_info(r)
    assert info_label(api) == "개성만두 궁"
    assert "주차 가능해?" in api.last_prompt() and "불가능" in api.last_prompt()


def test_clarify_then_name_with_own_field_uses_own_field(real_catalog):
    """되묻기 뒤 '대원군별장 주차는?'처럼 새 정보를 물으면 그 정보로 (앞 질문 '요금'이 아님)."""
    api = Api(real_catalog)
    api.say("무료 입장이야?")
    r = api.say("대원군별장 주차 돼?")
    assert_place_info(r)
    assert "주차 정보는 없어요" in r["answer"] and "요금" not in r["answer"]


def test_clarify_then_new_request_is_normal(real_catalog):
    """되묻기 뒤 장소 이름이 아닌 새 요청은 평소처럼 추천."""
    api = Api(real_catalog)
    api.say("무료 입장이야?")
    r = api.say("명동 맛집 추천해줘")
    assert r["center"]["label"] == "명동" and r["places"]


def test_clarify_carry_only_once(real_catalog):
    """이어받기는 되묻기 바로 다음 한 번만: 그다음 이름만 말하면 그 장소 근처 추천."""
    api = Api(real_catalog)
    api.say("무료 입장이야?")
    assert_place_info(api.say("대원군별장"))
    r = api.say("길상사")
    assert r["center"]["source"] == "place" and r["center"]["label"] == GILSANG and r["places"]


def test_clarify_then_name_history_format(real_catalog):
    """기록: user '대원군별장' → assistant center=석파정(place), places []."""
    api = Api(real_catalog)
    api.say("무료 입장이야?")
    api.say("대원군별장")
    msgs = api.history()
    assert [m["role"] for m in msgs] == ["user", "assistant"] * 2
    assert msgs[1]["message"] == CLARIFY_ANSWER and msgs[1]["center"] is None
    assert msgs[3]["center"]["source"] == "place" and msgs[3]["center"]["label"] == SEOKPA
    assert msgs[3]["places"] == []
