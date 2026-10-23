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
    assert "질문9" in prompt and "질문3" not in prompt  # 최근 6개만
    assert "광화문 근처 맛집" in prompt


def test_build_prompt_without_note():
    prompt = build_prompt("맛집", [], [_place("A")], None, None)
    assert "A" in prompt
    assert "km 떨어진" not in prompt


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
