"""질문 의도(맛집/카페/관광/축제)와 일상 대화 판별 — 키워드 기반."""
from dataclasses import dataclass, field

from app.catalog import CAFE_CAT3, EVENT_TYPE, FOOD_TYPE

TOUR_TYPES = {"12", "14", "28", "38"}
ALL_TYPES = TOUR_TYPES | {FOOD_TYPE}

FOOD_KEYWORDS = ("맛집", "식당", "음식", "먹", "밥", "점심", "저녁")
CAFE_KEYWORDS = ("카페", "커피", "디저트", "찻집")
TOUR_KEYWORDS = ("관광", "명소", "볼거리", "가볼", "구경", "놀거리", "데이트")
FESTIVAL_KEYWORDS = ("축제", "행사", "공연")

# 기존 main.py 그대로
CASUAL_KEYWORDS = (
    "고마워", "감사", "고맙", "땡큐", "thanks",
    "ㅎㅎ", "ㅋㅋ", "좋아", "최고", "완벽", "대박", "진짜", "정말", "너무", "굿",
    "꼭 가볼게", "다녀올게", "가봐야겠다", "가볼게", "가야겠다", "방문해볼게",
    "다음에 또", "또 올게", "다음에 올게", "잘가", "bye", "안녕",
    "도움", "유용", "덕분", "알려줘서", "추천해줘서", "참고",
)

CASUAL_RESPONSES = (
    "별말씀을요 😊 서울 여행 즐겁게 하세요!",
    "도움이 됐다니 정말 다행이에요 🙌",
    "감사해요! 언제든지 궁금한 거 물어보세요 😄",
    "저도 즐거웠어요! 좋은 여행 되세요 ✨",
    "꼭 좋은 시간 보내고 오세요!💕",
    "분명 마음에 드실 거예요! 다녀오시면 어땠는지 알려주세요 😊",
    "좋은 선택이에요! 즐거운 시간 되시길 바랍니다 🎉",
    "언제든지 환영해요! 더 궁금한 거 생기면 또 와주세요 😊",
    "다음에 또 오세요! 서울 구석구석 더 알려드릴게요 😉",
    "기다리고 있을게요! 즐거운 하루 되세요 😄",
    "과찬이세요 😊 더 도움이 필요하면 언제든지요!",
    "감사해요! 서울 여행이 더 즐거워지길 바라요 ✨",
)


@dataclass
class Intent:
    content_types: set[str] = field(default_factory=lambda: set(ALL_TYPES))
    cat3: str | None = None
    casual: bool = False


def _has(message: str, keywords) -> bool:
    lowered = message.lower()
    return any(k in lowered for k in keywords)


def detect_intent(message: str) -> Intent:
    food = _has(message, FOOD_KEYWORDS)
    cafe = _has(message, CAFE_KEYWORDS)
    tour = _has(message, TOUR_KEYWORDS)
    festival = _has(message, FESTIVAL_KEYWORDS)

    if not (food or cafe or tour or festival) and _has(message, CASUAL_KEYWORDS):
        return Intent(content_types=set(), cat3=None, casual=True)

    wants_food = food or cafe
    if festival and not wants_food and not tour:
        # "이번 주 축제"처럼 축제·행사만 물으면 축제/행사만
        return Intent(content_types={EVENT_TYPE}, cat3=None, casual=False)

    if wants_food and not tour:
        types = {FOOD_TYPE}
    elif tour and not wants_food:
        types = set(TOUR_TYPES)
    else:
        types = set(ALL_TYPES)
    if festival:
        types.add(EVENT_TYPE)

    cat3 = CAFE_CAT3 if (cafe and not food and not tour) else None
    return Intent(content_types=types, cat3=cat3, casual=False)
