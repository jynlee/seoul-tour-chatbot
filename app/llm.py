"""답변 문장 생성 (Ollama). 장소 목록은 LLM이 아니라 카탈로그에서 만든다."""
from typing import Protocol

from app.schemas import PlaceOut

HISTORY_LIMIT = 6


class LLMUnavailable(RuntimeError):
    """Ollama가 꺼졌거나 느리거나 빈 답을 줌 → 템플릿 답변으로 대체."""


class LLM(Protocol):
    def generate(self, prompt: str) -> str: ...


def _place_line(i: int, p: PlaceOut) -> str:
    line = f"{i}. 이름: {p.title} / 분류: {p.category} / 주소: {p.addr}"
    if p.walk_min is not None:
        line += f" / 도보 {p.walk_min}분"
    return line


def build_prompt(message: str, history_texts: list[str], places: list[PlaceOut],
                 center_label: str | None, fallback_note: str | None) -> str:
    history = "\n".join(history_texts[-HISTORY_LIMIT:]) or "(없음)"
    place_text = "\n".join(_place_line(i, p) for i, p in enumerate(places, 1)) or "(없음)"
    rules = [
        "1. 반드시 한국어로, 2문장 이내로만 답변할 것",
        "2. 아래 [추천 장소]에 있는 장소만 언급하고, 목록에 없는 장소를 지어내지 말 것",
        "3. 추천 장소가 없으면 \"조건에 맞는 장소를 찾지 못했어요.\"라고만 답할 것",
        "4. 친근한 말투로, 장소 목록은 지도에 표시된다는 점을 고려해 핵심만 말할 것",
        "5. 날짜·기간·영업시간·가격·메뉴처럼 [추천 장소]에 없는 정보는 말하지 말 것",
    ]
    if fallback_note:
        rules.append(f"6.기준점 반경 안에 장소가 없어서 가까운 곳을 골랐다. 다음 문장을 반드시 언급할 것: \"{fallback_note}\"")
    rules_text = "\n".join(rules)
    center_text = center_label or "(기준점 없음)"
    return f"""너는 서울 관광 안내 챗봇 "서울 여행 친구"야. 반드시 한국어로만 답변해.

규칙:
{rules_text}

[이전 대화]
{history}

[기준점]
{center_text}

[추천 장소]
{place_text}

[현재 질문]
{message}

[답변] (2문장 이내로)"""


def template_answer(places: list[PlaceOut], center_label: str | None) -> str:
    if not places:
        return "조건에 맞는 장소를 찾지 못했어요. 다른 지역이나 종류로 물어봐 주세요."
    names = ", ".join(p.title for p in places)
    if center_label:
        return f"{center_label} 근처 추천 장소를 지도에 표시했어요: {names}"
    return f"추천 장소를 지도에 표시했어요: {names}"


class OllamaLLM:
    def __init__(self, settings, timeout: float = 30):
        self._url = settings.ollama_url.rstrip("/")
        self._model = settings.ollama_model
        self._timeout = timeout

    def generate(self, prompt: str) -> str:
        import requests

        try:
            resp = requests.post(
                f"{self._url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.3, "top_p": 0.9},
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            text = (resp.json().get("response") or "").strip()
        except Exception as e:
            raise LLMUnavailable(str(e)) from e
        if not text:
            raise LLMUnavailable("빈 답변")
        return text

    def ping(self) -> bool:
        import requests

        try:
            resp = requests.get(f"{self._url}/api/tags", timeout=3)
            resp.raise_for_status()
            names = {m.get("name") for m in resp.json().get("models", [])}
            return self._model in names
        except Exception:
            return False
