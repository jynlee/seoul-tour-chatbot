"""추천 코스: 질문이 코스인지 판정하고, 칸(맛집·카페·관광지…) 순서를 정한다 — 순수 함수, 키워드 기반."""
import re
from dataclasses import dataclass

from app.catalog import CAFE_CAT3, EVENT_TYPE, FOOD_TYPE
from app.intent import (
    CAFE_KEYWORDS, FESTIVAL_KEYWORDS, FOOD_KEYWORDS, TOUR_TOPICS, TOUR_TYPES, has_word,
)

COURSE_WORDS = ("코스", "동선", "루트", "일정 짜", "하루 일정", "순서대로")
DATE_WORDS = ("데이트", "기념일", "연인", "여자친구", "남자친구")
# 데이트는 빼고 본다 ('데이트'는 intent 관광 키워드에 있어 종류 말로 오인된다)
GENERIC_TOUR_WORDS = ("관광", "명소", "볼거리", "가볼", "구경", "놀거리")
MAX_STEPS = 4
MIN_STEPS = 3
_HANGUL = re.compile(r"[가-힣]")

SIGHT_TYPES = frozenset({"12", "14"})
# 관광 주제 → 칸 이름 (야경은 별도 칸 정의)
TOPIC_STEP_LABELS = {
    "night": "야경", "nature": "산책", "history": "역사",
    "culture": "전시", "shopping": "쇼핑", "activity": "체험",
}
TOPIC_STEP_TYPES = {
    "nature": SIGHT_TYPES, "history": SIGHT_TYPES, "culture": SIGHT_TYPES,
    "shopping": frozenset({"38"}), "activity": frozenset({"12", "28"}),
}


@dataclass(frozen=True)
class Step:
    label: str
    content_types: frozenset[str]
    cat3: str | None = None          # 카페만 CAFE_CAT3
    exclude_cat3: str | None = None  # 맛집 칸은 카페 제외
    topic: str | None = None         # TOUR_TOPICS 키
    required_topic: bool = False     # 야경: 주제에 맞는 곳만
    quiet_drop: bool = False         # 야경: 빠져도 안내 안 함


@dataclass(frozen=True)
class CoursePlan:
    theme: str  # "date" | "shopping_food" | "custom" | "default"
    steps: tuple[Step, ...]


SIGHT = Step("볼거리", SIGHT_TYPES)
TOURSPOT = Step("관광지", SIGHT_TYPES)
FOOD = Step("맛집", frozenset({FOOD_TYPE}), exclude_cat3=CAFE_CAT3)
CAFE = Step("카페", frozenset({FOOD_TYPE}), cat3=CAFE_CAT3)
NIGHT = Step("야경", frozenset(TOUR_TYPES), topic="night", required_topic=True, quiet_drop=True)
FESTIVAL = Step("축제", frozenset({EVENT_TYPE}))


def _topic_step(key: str) -> Step:
    if key == "night":
        return NIGHT
    return Step(TOPIC_STEP_LABELS[key], TOPIC_STEP_TYPES[key], topic=key)


def _word_pos(text: str, word: str) -> int | None:
    """말이 낱말로 나온 첫 위치. 한 글자 말은 앞이 한글이면 장소 이름의 일부('경복궁'의 '궁')라 뺀다."""
    start = 0
    while (i := text.find(word, start)) != -1:
        if len(word) > 1:
            return i
        if (i == 0 or not _HANGUL.match(text[i - 1])) and has_word(text[i:], word):
            return i
        start = i + 1
    return None


def _first_pos(text: str, words) -> int | None:
    """말들 중 문장에서 가장 앞에 나온 위치 (없으면 None)."""
    found = [p for p in (_word_pos(text, w) for w in words) if p is not None]
    return min(found) if found else None


def _kind_steps(message: str) -> list[Step]:
    """데이트 말을 뺀 문장에서 장소 종류 말 → 문장 속 위치 순서의 칸 (같은 칸 중복 없음)."""
    text = message.lower()
    for w in DATE_WORDS:
        text = text.replace(w, " ")
    found: list[tuple[int, Step]] = []

    def add(pos, step):
        if pos is not None:
            found.append((pos, step))

    add(_first_pos(text, FOOD_KEYWORDS), FOOD)
    add(_first_pos(text, CAFE_KEYWORDS), CAFE)
    add(_first_pos(text.replace("공연장", "  "), FESTIVAL_KEYWORDS), FESTIVAL)
    add(_first_pos(text, GENERIC_TOUR_WORDS), TOURSPOT)
    topic_pos = {}
    for key, t in TOUR_TOPICS.items():
        words = [k for k in t.keywords if _word_pos(text, k) is not None]
        if words:
            topic_pos[key] = (_first_pos(text, words), words)
    # '한강 야경'의 '한강'은 장소 이름일 뿐 → 야경이 있으면 한강만으로 산책 칸을 만들지 않는다
    if "night" in topic_pos and "nature" in topic_pos and set(topic_pos["nature"][1]) <= {"한강"}:
        del topic_pos["nature"]
    for key, (pos, _) in topic_pos.items():
        add(pos, _topic_step(key))
    found.sort(key=lambda x: x[0])
    steps: list[Step] = []
    for _, s in found:
        if s not in steps:
            steps.append(s)
    return steps


def plan_course(message: str) -> CoursePlan | None:
    """코스 질문이면 칸 계획, 아니면 None(단일 추천)."""
    has_course = any(w in message for w in COURSE_WORDS)
    has_date = any(w in message for w in DATE_WORDS)
    kinds = _kind_steps(message)
    if kinds:
        if not has_course:
            return None
        labels = {s.label for s in kinds}
        if labels == {"쇼핑", "맛집"}:
            return CoursePlan("shopping_food", (_topic_step("shopping"), FOOD, CAFE))
        steps = kinds[:MAX_STEPS]
        # 3칸 미만이면 없는 것(맛집 → 카페)을 뒤에 붙인다
        for extra in (FOOD, CAFE):
            if len(steps) < MIN_STEPS and extra not in steps:
                steps.append(extra)
        # 그래도 3칸 미만이면 관광지를 맨 앞에
        if len(steps) < MIN_STEPS and TOURSPOT not in steps:
            steps.insert(0, TOURSPOT)
        return CoursePlan("custom", tuple(steps))
    if has_date:
        return CoursePlan("date", (SIGHT, FOOD, CAFE, NIGHT))
    if has_course:
        return CoursePlan("default", (TOURSPOT, FOOD, TOURSPOT, CAFE))
    return None


def is_course_question(message: str) -> bool:
    return plan_course(message) is not None
