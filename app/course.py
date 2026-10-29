"""추천 코스: 질문이 코스인지 판정하고, 칸(맛집·카페·관광지…) 순서를 정한다 — 순수 함수, 키워드 기반."""
import re
from dataclasses import dataclass

from app.catalog import CAFE_CAT3, EVENT_TYPE, FOOD_TYPE, Place, has_coords
from app.center import AREA_LIKE_TITLES, Center
from app.geo import haversine_m, walk_min
from app.intent import (
    CAFE_KEYWORDS, FESTIVAL_KEYWORDS, FOOD_KEYWORDS, TOUR_TOPICS, TOUR_TYPES, has_word,
    matches_topic, title_has_topic_word, topic_words,
)
from app.recommend import CANDIDATES_K, CENTER_GROUP_RADIUS_M, _gu_of_center, group_key, one_per_group, to_place_out
from app.schemas import PlaceOut

COURSE_WORDS = ("코스", "동선", "루트", "일정 짜", "하루 일정", "순서대로")
DATE_WORDS = ("데이트", "기념일", "연인", "여자친구", "남자친구")
# 데이트는 빼고 본다 ('데이트'는 intent 관광 키워드에 있어 종류 말로 오인된다)
GENERIC_TOUR_WORDS = ("관광", "명소", "볼거리", "가볼", "구경", "놀거리")
MAX_STEPS = 4
MIN_STEPS = 3
_HANGUL = re.compile(r"[가-힣]")
# 걷기 코스 이름('[종로둘레길 3코스] 낙산 코스')은 코스의 한 칸(장소)이 아님
_WALK_COURSE_TITLE = re.compile(r"둘레길|코스\s*$|관광특구")  # 관광특구는 지역 묶음

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


# 코스 야경 칸 전용 제목 검사 (intent 의 night 패턴은 추천용이라 그대로 둠, Ruling 8·10)
_NIGHT_OK = re.compile(r"(?:대교|다리)(?=$|[\s(])|타워|전망|루프탑|야경|분수|스카이|한강공원|물빛광장")
_NIGHT_NO = re.compile(r"수영장|물놀이|교당|성당|교회|사찰|도서관|(?<![가-힣])절(?![가-힣])")


def _night_title(p: Place, step: Step) -> bool:
    return _NIGHT_OK.search(p.title) is not None and _NIGHT_NO.search(p.title) is None


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


def _first_pos(text: str, words, topic: bool = False) -> int | None:
    """말들 중 문장에서 가장 앞에 나온 위치 (없으면 None). topic이면 한 글자 말 규칙(_word_pos), 아니면 그냥 부분 문자열."""
    find = _word_pos if topic else (lambda t, w: t.find(w) if w in t else None)
    found = [p for p in (find(text, w) for w in words) if p is not None]
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
            topic_pos[key] = (_first_pos(text, words, topic=True), words)
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


# '둘레길 코스'·'등산 코스'처럼 산책 주제 말 바로 뒤의 '코스'는 걷는 길 이름이지 하루 일정이 아님 (Ruling 11)
_TRAIL_COURSE = re.compile(r"(?:둘레길|등산|산책|걷기|트레킹)\s?코스")


def _is_trail_course(message: str) -> bool:
    """'둘레길 코스' 등만 있고 다른 칸 말·데이트 말이 없으면 True (단일 추천)."""
    if not _TRAIL_COURSE.search(message) or any(w in message for w in DATE_WORDS):
        return False
    rest = _TRAIL_COURSE.sub(" ", message)
    return not _kind_steps(rest) and not any(w in rest for w in COURSE_WORDS)


def plan_course(message: str) -> CoursePlan | None:
    """코스 질문이면 칸 계획, 아니면 None(단일 추천)."""
    if _is_trail_course(message):
        return None
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


NEXT_RADIUS_M = 800        # 다음 칸은 직전 장소에서 이만큼 안
WIDE_RADIUS_M = 1500       # 800m 안에 없을 때(첫 칸의 기준점 반경도 이 값)
MAX_TOTAL_WALK_M = 3000    # 칸 사이 걷는 거리 합
MIN_STOPS = 3


@dataclass
class CourseResult:
    places: list[PlaceOut]  # step·leg_m·leg_walk_min 채움, 코스 순서
    dropped: list[str]      # 답에서 안내할 빠진 칸 이름 (quiet_drop 칸 제외)
    ok: bool                # len(places) >= MIN_STOPS


def build_course(message: str, plan: CoursePlan, center: Center | None, searcher, embedder,
                 catalog: dict[str, Place], exclude_ids: set[str] | frozenset = frozenset()) -> CourseResult:
    """칸 계획대로 장소를 고른다: 첫 칸은 기준점 근처, 다음 칸은 직전 장소 800m → 1.5km 안, 없으면 그 칸을 뺀다."""
    skip = set(exclude_ids)
    center_place = catalog.get(center.place_id) if center is not None and getattr(center, "place_id", None) else None
    if center_place is not None:
        skip.add(center_place.id)
    center_key = group_key(center_place.title) if center_place is not None and center_place.kind != "food" else None
    gu = _gu_of_center(center)

    def part_of_center(p: Place) -> bool:
        # recommend 와 같은 규칙: 종류가 같은 세부 장소만 (이름만 빌린 별개 장소는 남김)
        return (center_key is not None and p.content_type == center_place.content_type
                and group_key(p.title) == center_key
                and haversine_m(center_place.lat, center_place.lng, p.lat, p.lng) <= CENTER_GROUP_RADIUS_M)

    chosen: list[Place] = []
    out: list[PlaceOut] = []
    dropped: list[str] = []
    walked = 0.0  # 칸 사이 걸은 거리 합

    for step in plan.steps:
        prev = chosen[-1] if chosen else None
        text = f"{message} 전시 산책 볼거리" if step.label == "볼거리" else f"{message} {step.label}"
        vector = embedder.encode(text)
        words = topic_words(message, step.topic)

        def boost(p: Place) -> int:
            return (2 if title_has_topic_word(p.title, words, step.topic) else 0) +                    (1 if matches_topic(p.category, p.title, step.topic) else 0)

        def usable(p: Place) -> bool:
            if p.id in skip or not has_coords(p) or p.id in {c.id for c in chosen}:
                return False
            if step.exclude_cat3 and p.cat3 == step.exclude_cat3:
                return False
            if part_of_center(p):
                return False
            if p.title in AREA_LIKE_TITLES:  # '홍대'처럼 지역 이름을 가진 장소는 장소가 아니라 지역 (Ruling 9)
                return False
            if step.content_types == SIGHT_TYPES and _WALK_COURSE_TITLE.search(p.title):
                return False
            # 야경은 제목으로만 (건축/조형물 분류만으로는 동상도 걸림, Ruling 8)
            if step.required_topic and not _night_title(p, step):
                return False
            # 묶음(큰 관광지의 세부 시설) 검사는 음식점끼리는 하지 않는다: "인사동 한정식"·"인사동 찻집"은 별개 가게
            pool = [c for c in chosen if c.kind != "food"] if p.kind == "food" else chosen
            return len(one_per_group(pool + [p])) == len(pool) + 1

        def candidates(near, extra=()) -> list[Place]:
            hits = searcher.knn(vector, step.content_types, step.cat3, CANDIDATES_K, near=near)
            found, seen = [], set()
            for pid, _score in hits:
                p = catalog.get(pid)
                if p is None or pid in seen or not usable(p):
                    continue
                seen.add(pid)
                found.append(p)
            for p in extra:  # kNN 상위에 없던 후보를 뒤에 붙임
                if p.id not in seen and usable(p):
                    seen.add(p.id)
                    found.append(p)
            found.sort(key=lambda p: -boost(p))  # 안정 정렬: 주제 맞는 곳 먼저, 그 안에서는 관련도순
            return found

        pick = None
        if prev is None:
            # 첫 칸(앞 칸이 빠졌어도 아직 못 골랐으면 같은 규칙): 구는 near 없이 그 구 안, 반경형은 1.5km, 기준점 없음은 서울 전체
            if gu is not None:
                # 구 이름과 같은 제목의 장소('강남')는 지역을 말한 것이라 뺌. kNN 상위에 없던 같은 구 장소도 뒤에 붙임(recommend 와 같음)
                def in_gu(p: Place) -> bool:
                    return p.gu == gu and p.title not in (gu, gu[:-1])

                found = [p for p in candidates(None, [p for p in catalog.values() if in_gu(p)]) if in_gu(p)]
            elif center is not None:
                found = candidates((center.lat, center.lng, WIDE_RADIUS_M))
            else:
                found = candidates(None)
            pick = found[0] if found else None
            leg = (haversine_m(center.lat, center.lng, pick.lat, pick.lng)
                   if pick is not None and center is not None and gu is None else None)
        else:
            leg = None
            for radius in (NEXT_RADIUS_M, WIDE_RADIUS_M):
                for p in candidates((prev.lat, prev.lng, radius)):
                    d = haversine_m(prev.lat, prev.lng, p.lat, p.lng)
                    if walked + d <= MAX_TOTAL_WALK_M:
                        pick, leg = p, d
                        break
                if pick is not None:
                    break
            if pick is not None:
                walked += leg

        if pick is None:
            if not step.quiet_drop:
                dropped.append(step.label)
            continue
        chosen.append(pick)
        po = to_place_out(pick)
        po.step = step.label
        if leg is not None:
            po.leg_m = int(round(leg))
            po.leg_walk_min = walk_min(po.leg_m)
        out.append(po)

    return CourseResult(places=out, dropped=dropped, ok=len(out) >= MIN_STOPS)
