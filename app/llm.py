"""답변 문장 생성 (Ollama). 장소 목록은 LLM이 아니라 카탈로그에서 만든다."""
from typing import Protocol

from app.schemas import PlaceOut

HISTORY_LIMIT = 8  # 약 4턴 (사용자+챗봇)


class LLMUnavailable(RuntimeError):
    """Ollama가 꺼졌거나 느리거나 빈 답을 줌 → 템플릿 답변으로 대체."""


class LLM(Protocol):
    def generate(self, prompt: str) -> str: ...


NEAR_RADIUS_M = 1500


def _place_line(i: int, p: PlaceOut, mark_far: bool = True) -> str:
    line = f"{i}. 이름: {p.title} / 분류: {p.category} / 주소: {p.addr}"
    if mark_far and p.walk_min is not None:
        line += f" / 도보 {p.walk_min}분"
    if mark_far and p.distance_m is not None and p.distance_m > NEAR_RADIUS_M:
        line += " / 기준점에서 조금 멂"
    return line


def all_far(places: list[PlaceOut]) -> bool:
    """모든 장소가 기준점 반경(1.5km) 밖인지 ("다른 데 더"에서 가까운 곳이 바닥난 경우)."""
    return bool(places) and all(p.distance_m is not None and p.distance_m > NEAR_RADIUS_M for p in places)


def mentions_missing(answer: str) -> bool:
    return any(w in answer for w in ("없", "못 찾", "어려", "아쉽"))


def mentions_far(answer: str) -> bool:
    return any(w in answer for w in ("떨어", "멀", "km"))


def build_prompt(message: str, history_texts: list[str], places: list[PlaceOut],
                 center_label: str | None, fallback_note: str | None, more: bool = False,
                 far_notice: str | None = None, topic_label: str | None = None, topic_missing: bool = False,
                 gu_wide: bool = False) -> str:
    """gu_wide: 구 전체에서 고른 결과 → 구 중심에서의 거리·'조금 멂' 표시는 의미가 없어 뺀다."""
    history = "\n".join(history_texts[-HISTORY_LIMIT:]) or "(없음)"
    place_text = "\n".join(_place_line(i, p, mark_far=not gu_wide) for i, p in enumerate(places, 1)) or "(없음)"
    rules = [
        "반드시 한국어로, 2문장 이내로만 답변할 것",
        "아래 [추천 장소]에 있는 장소만 언급하고, 목록에 없는 장소를 지어내지 말 것",
        "[이전 대화]에 나온 장소는 이번 답변에서 다시 추천하지 말 것. [이전 대화]는 흐름을 이어 가는 데만 쓸 것",
        "추천 장소가 없으면 \"조건에 맞는 장소를 찾지 못했어요.\"라고만 답할 것",
        "친근한 말투로, 장소 목록은 지도에 표시된다는 점을 고려해 핵심만 말할 것",
        "날짜·기간·영업시간·가격·메뉴처럼 [추천 장소]에 없는 정보는 말하지 말 것",
    ]
    if center_label:
        rules.append(f"위치를 말할 때는 [기준점]인 '{center_label}'만 쓰고, 이전 대화에 나온 다른 지역 이름을 쓰지 말 것")
        if not gu_wide:  # 구 결과는 장소 줄에 거리 표시가 없음
            rules.append("'기준점에서 조금 멂'이라고 표시된 장소는 '근처'라고 하지 말고 조금 떨어져 있다고 말할 것")
    else:
        rules.append("기준점이 없으므로 '근처'·'주변'이라는 말이나 특정 동네·지역 이름을 쓰지 말 것")
        rules.append("답변 끝에 현재 위치(📍)를 켜거나 지역 이름을 말해 주면 더 가까운 곳을 찾아 준다고 안내할 것")
    if gu_wide:
        rules.append(f"[추천 장소]는 {center_label} 안에서 고른 곳이니 '{center_label}에 있는'처럼 말하고 거리 얘기는 하지 말 것")
    if topic_label and topic_missing:
        rules.append(f"[추천 장소]에는 '{topic_label}'에 딱 맞는 곳이 없다. 첫 문장에서 이 점을 솔직히 말하고, "
                     "대신 비슷한 관광지를 골랐다고 말할 것. 장소를 산책·공원 등으로 포장하지 말 것")
    elif topic_label:
        rules.append(f"질문 주제는 '{topic_label}'이다. [추천 장소] 중 이 주제에 맞는 곳(분류·이름으로 판단)을 먼저 소개할 것")
    if more:
        rules.append("사용자가 다른 곳을 원했다. [추천 장소]는 이전에 보여 준 곳을 뺀 새 장소들이라는 점을 자연스럽게 말할 것")
    if far_notice:
        rules.append(f"'{center_label}' 1.5km 안에는 더 보여드릴 곳이 없어서 떨어진 곳을 골랐다. "
                     "첫 문장에서 이 사실(떨어져 있다는 점)을 솔직히 말하고, '기준점'이라는 단어는 쓰지 말 것")
    if fallback_note:
        rules.append(f"기준점 반경 안에 장소가 없어서 가까운 곳을 골랐다. 다음 문장을 반드시 언급할 것: \"{fallback_note}\"")
    rules_text = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
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


CLARIFY_ANSWER = "어느 곳을 말씀하시는지 알려주세요. 장소 이름을 말하거나 지도에서 핀을 눌러 주시면 알려드릴게요."
NO_MORE_ANSWER = "{label} 조건으로 더 보여드릴 곳이 없어요. 다른 지역이나 종류로 물어봐 주세요."
ORDINAL_OUT_OF_RANGE = "목록에는 {n}곳까지 있어요. 몇 번째 장소인지 다시 알려 주세요."
TOPIC_MISSING_NOTICE = "{where}{topic}에 딱 맞는 곳은 못 찾아서 비슷한 관광지를 골랐어요."
FAR_MORE_NOTICE = "{label} 근처(1.5km 안)에는 더 보여드릴 곳이 없어서 조금 떨어진 곳을 골랐어요."


def _labels():
    from app.dialog import FIELD_LABELS

    return FIELD_LABELS


def _place_facts(place) -> list[str]:
    labels = _labels()
    facts = [f"이름: {place.title}", f"분류: {place.category}", f"주소: {place.addr}",
             f"전화: {place.tel or '정보 없음'}"]
    for key, value in place.detail.items():
        if value:
            facts.append(f"{labels.get(key, key)}: {value}")
    return facts


def build_info_prompt(message: str, history_texts: list[str], place, fields: list[str]) -> str:
    """장소 하나에 대한 정보 질문(주차·영업시간·어디야 등). 근거는 이 장소의 기본 정보와 detail 뿐."""
    labels = _labels()
    history = "\n".join(history_texts[-HISTORY_LIMIT:]) or "(없음)"
    facts = "\n".join(f"- {f}" for f in _place_facts(place))
    asked = ", ".join(labels.get(f, f) for f in fields) or "(장소 소개)"
    tel_rule = f"전화({place.tel})로 확인해 보라고 덧붙일 것" if place.tel else "확인할 전화번호도 없다고 말할 것"
    rules = [
        "반드시 한국어로, 1~2문장으로만 답변할 것",
        f"[장소 정보]에 있는 내용만 근거로 '{place.title}'에 대해 답할 것. 다른 장소를 추천하거나 지어내지 말 것",
        f"물어본 항목이 [장소 정보]에 없으면 지어내지 말고 '○○ 정보는 없어요'라고 말한 뒤 {tel_rule}",
        "이전 대화는 말투와 흐름을 맞추는 데만 쓰고, 사실 근거로 쓰지 말 것",
    ]
    rules_text = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    return f"""너는 서울 관광 안내 챗봇 "서울 여행 친구"야. 반드시 한국어로만 답변해.

규칙:
{rules_text}

[이전 대화]
{history}

[장소 정보]
{facts}

[물어본 항목]
{asked}

[현재 질문]
{message}

[답변] (1~2문장으로)"""


def info_template_answer(place, fields: list[str]) -> str:
    """LLM 없이 detail 값을 그대로 쓴 답변 (Ollama 다운, 또는 물어본 정보가 하나도 없을 때)."""
    from app.dialog import info_value

    labels = _labels()
    if not fields:
        answer = f"{place.title}: {place.category}, 주소 {place.addr}"
        answer += f", 전화 {place.tel}." if place.tel else "."
        return answer
    parts, missing = [], False
    for f in fields:
        value = info_value(place, f)
        if value:
            parts.append(f"{labels.get(f, f)}: {value}")
        else:
            parts.append(f"{labels.get(f, f)} 정보는 없어요")
            missing = True
    answer = f"{place.title} — " + " / ".join(parts) + "."
    if missing and place.tel:
        answer += f" 전화({place.tel})로 확인해 보세요."
    return answer


def template_answer(places: list[PlaceOut], center_label: str | None, far: bool = False) -> str:
    if not places:
        return "조건에 맞는 장소를 찾지 못했어요. 다른 지역이나 종류로 물어봐 주세요."
    names = ", ".join(p.title for p in places)
    if far:
        return f"추천 장소를 지도에 표시했어요: {names}"
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
