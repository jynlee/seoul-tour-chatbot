import pytest

from app.llm import LLMUnavailable, OllamaLLM, build_prompt, template_answer
from app.schemas import PlaceOut


def _place(title, walk=None):
    return PlaceOut(id=title, title=title, kind="food", category="한식", addr="서울 종로구", tel="",
                    lat=37.57, lng=126.98, image="", distance_m=None if walk is None else walk * 67, walk_min=walk)


def test_build_prompt_contents():
    places = [_place("개성만두 궁", 12), _place("광화문 세종클럽", 6)]
    history = [f"사용자: 질문{i}" for i in range(10)]
    prompt = build_prompt("광화문 근처 맛집", history, places, "광화문", "가장 가까운 곳은 2.3km 떨어진 개성만두 궁예요")
    assert "개성만두 궁" in prompt and "광화문 세종클럽" in prompt
    assert "2문장" in prompt
    assert "도보 12분" in prompt
    assert "가장 가까운 곳은 2.3km 떨어진 개성만두 궁예요" in prompt
    assert "반드시" in prompt
    assert "질문9" in prompt and "질문2" in prompt and "질문1" not in prompt  # 최근 8개(약 4턴)만
    assert "광화문 근처 맛집" in prompt


def test_build_prompt_without_note():
    prompt = build_prompt("맛집", [], [_place("A")], None, None)
    assert "A" in prompt
    assert "km 떨어진" not in prompt


def test_build_prompt_no_center_forbids_nearby():
    # QA-2: 기준점이 없으면 "근처·주변"이라고 하지 말고 위치·지역을 알려 달라고 안내
    prompt = build_prompt("내 주변 맛집", [], [_place("A")], None, None)
    assert "근처" in prompt and "주변" in prompt and "쓰지 말 것" in prompt
    assert "지역" in prompt


def test_build_prompt_center_label_and_far_mark():
    # QA-2: 기준점 이름은 [기준점] 값만, 반경 밖으로 채운 곳은 '조금 멂' 표시
    far = _place("먼카페", 35)  # 35*67 = 2345m
    prompt = build_prompt("거기 근처 카페 있어?", ["챗봇: 광화문 근처 맛집이에요"], [_place("가까운카페", 6), far],
                          "광화문국밥", None)
    assert "'광화문국밥'" in prompt
    assert "조금 멂" in prompt
    lines = prompt.splitlines()
    assert "조금 멂" in next(l for l in lines if "먼카페" in l)
    assert "조금 멂" not in next(l for l in lines if "가까운카페" in l)


def test_build_prompt_history_not_a_source_and_more_hint():
    prompt = build_prompt("다른 데 더 추천해줘", ["챗봇: 감꽃당 추천 [보여 준 장소: 감꽃당]"], [_place("개뿔", 40)],
                          "명동", None, more=True)
    assert "[이전 대화]에 나온 장소" in prompt
    assert "이전에 보여 준 곳을 뺀 새 장소" in prompt
    assert "이전에 보여 준 곳을 뺀" not in build_prompt("맛집", [], [_place("A")], "명동", None)


def test_template_answer():
    places = [_place("A"), _place("B"), _place("C")]
    assert template_answer(places, "광화문") == "광화문 근처 추천 장소를 지도에 표시했어요: A, B, C"
    assert template_answer(places, None) == "추천 장소를 지도에 표시했어요: A, B, C"
    assert template_answer([], "광화문") == "조건에 맞는 장소를 찾지 못했어요. 다른 지역이나 종류로 물어봐 주세요."


def test_ollama_unreachable_raises():
    class S:
        ollama_url = "http://127.0.0.1:9"
        ollama_model = "gemma4:e4b"

    with pytest.raises(LLMUnavailable):
        OllamaLLM(S(), timeout=2).generate("안녕")


def test_mentions_missing():
    from app.llm import mentions_missing

    assert mentions_missing("산책이나 자연 위주의 장소는 찾기 어려워요.")
    assert mentions_missing("아쉽게도 공원은 없지만")
    assert not mentions_missing("강서구에 있는 곳들이에요.")
