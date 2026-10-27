"""질문 의도(맛집/카페/관광/축제)와 일상 대화 판별 — 키워드 기반."""
import re
from dataclasses import dataclass, field

from app.catalog import CAFE_CAT3, EVENT_TYPE, FOOD_TYPE

TOUR_TYPES = {"12", "14", "28", "38"}
ALL_TYPES = TOUR_TYPES | {FOOD_TYPE}

FOOD_KEYWORDS = ("맛집", "식당", "음식", "먹", "밥", "점심", "저녁")
CAFE_KEYWORDS = ("카페", "커피", "디저트", "찻집")
TOUR_KEYWORDS = ("관광", "명소", "볼거리", "가볼", "구경", "놀거리", "데이트")
FESTIVAL_KEYWORDS = ("축제", "행사", "공연")


@dataclass(frozen=True)
class Topic:
    """관광 세부 주제: 질문 키워드 → 맞는 분류(cat2 한글명)·제목 패턴 (추천에서 앞쪽으로 끌어올림)."""
    label: str
    keywords: tuple[str, ...]
    categories: frozenset[str]
    title_pattern: str
    exclude_pattern: str = ""  # 제목 패턴에 걸려도 주제와 거리가 먼 곳 ('숲으로도서관', '한강 수영장')


# 순서대로 첫 번째로 맞는 주제 ("밤 산책"은 야경)
TOUR_TOPICS: dict[str, Topic] = {
    "night": Topic("야경", ("야경", "전망", "밤에", "밤 산책", "노을"), frozenset({"건축/조형물"}),
                   r"타워|전망|대교|다리|루프탑|한강"),
    "nature": Topic("산책·자연", ("산책", "공원", "걷기", "걷고", "걸을", "숲", "등산", "둘레길", "한강", "자연", "호수",
                               "트레킹", "피크닉", "소풍", "생태"),
                    frozenset({"자연관광지"}),  # 휴양관광지는 공원 외에 미로·스파도 섞여 있어 제목으로만 판단
                    r"공원|숲|둘레길|한강|호수|습지|수목원|정원|생태|(?:산|천|길|봉)(?:$|\s|\()",
                    r"도서관|수영장|물놀이장|시장|책방|드론|레져|익스트림|스파"),
    "history": Topic("역사", ("역사", "궁", "고궁", "유적", "한옥", "성곽", "왕릉", "문화재"), frozenset({"역사관광지"}),
                     r"궁|성곽|왕릉|한옥|향교|서원|문(?:$|\s)"),
    "culture": Topic("문화·전시", ("박물관", "미술관", "전시", "갤러리", "문화시설", "공연장"), frozenset({"문화시설"}),
                     r"박물관|미술관|갤러리|기념관|전시"),
    "shopping": Topic("쇼핑", ("쇼핑", "시장", "백화점", "아울렛", "쇼핑몰", "기념품"), frozenset({"쇼핑"}),
                      r"시장|백화점|아울렛|몰"),
    "activity": Topic("체험·레포츠", ("체험", "레포츠", "운동", "클라이밍", "스포츠", "액티비티", "만들기", "공방"),
                      frozenset({"체험관광지", "육상레포츠", "수상레포츠", "복합레포츠", "항공레포츠"}), r"체험|공방"),
}

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
    has_category: bool = False  # 질문에 맛집·카페·관광·축제 키워드가 실제로 있었는지 (없으면 직전 턴에서 이어받음)
    topic: str | None = None  # 관광 세부 주제 (TOUR_TOPICS 키)


# 한 글자 단어('궁')는 '궁금'처럼 다른 낱말 속에 흔히 들어간다 → 뒤가 끝·한글 아님·조사일 때만 인정
_PARTICLES = ("은", "는", "이", "가", "을", "를", "에", "도", "만", "로", "으로", "랑", "의", "였")
_HANGUL = re.compile(r"[가-힣]")


def has_word(message: str, word: str) -> bool:
    if len(word) > 1:
        return word in message
    for m in re.finditer(re.escape(word), message):
        rest = message[m.end():]
        if not rest or not _HANGUL.match(rest[0]) or rest.startswith(_PARTICLES):
            return True
    return False


def _has(message: str, keywords) -> bool:
    lowered = message.lower()
    return any(k in lowered for k in keywords)


def detect_topic(message: str) -> str | None:
    return next((key for key, t in TOUR_TOPICS.items() if any(has_word(message, k) for k in t.keywords)), None)


def topic_words(message: str, topic: str | None) -> list[str]:
    """질문에 나온 그 주제의 말 ('궁이나 박물관', 역사 → ['궁']). 다른 주제 말('한강 야경'의 '한강')은 뺀다."""
    if topic is None:
        return []
    return [k for k in TOUR_TOPICS[topic].keywords if has_word(message, k)]


def title_has_topic_word(title: str, words: list[str], topic: str | None) -> bool:
    """제목에 질문의 주제 말이 낱말로 있는지 ('무궁화동산'의 '궁'은 아님). 주제의 제외 패턴에 걸리면 아님."""
    if topic is None or not words:
        return False
    t = TOUR_TOPICS[topic]
    if t.exclude_pattern and re.search(t.exclude_pattern, title):
        return False
    return any(has_word(title, w) for w in words)


def matches_topic(category: str, title: str, topic: str | None) -> bool:
    if topic is None:
        return False
    t = TOUR_TOPICS[topic]
    if t.exclude_pattern and re.search(t.exclude_pattern, title):
        return False
    return category in t.categories or re.search(t.title_pattern, title) is not None


def detect_intent(message: str) -> Intent:
    food = _has(message, FOOD_KEYWORDS)
    cafe = _has(message, CAFE_KEYWORDS)
    tour = _has(message, TOUR_KEYWORDS)
    festival = _has(message, FESTIVAL_KEYWORDS)
    # 산책·공원·박물관… 같은 세부 주제도 관광으로 본다. 단 "한강 근처 맛집"처럼 음식과 같이 오면 장소 이름일 뿐.
    topic = None if (food or cafe) else detect_topic(message)
    tour = tour or topic is not None

    if not (food or cafe or tour or festival) and _has(message, CASUAL_KEYWORDS):
        return Intent(content_types=set(), cat3=None, casual=True)

    wants_food = food or cafe
    if festival and not wants_food and not tour:
        # "이번 주 축제"처럼 축제·행사만 물으면 축제/행사만
        return Intent(content_types={EVENT_TYPE}, cat3=None, casual=False, has_category=True)

    if wants_food and not tour:
        types = {FOOD_TYPE}
    elif tour and not wants_food:
        types = set(TOUR_TYPES)
    else:
        types = set(ALL_TYPES)
    if festival:
        types.add(EVENT_TYPE)

    cat3 = CAFE_CAT3 if (cafe and not food and not tour) else None
    return Intent(content_types=types, cat3=cat3, casual=False, has_category=wants_food or tour or festival,
                  topic=topic)
