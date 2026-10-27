"""공통 픽스처: 작은 카탈로그와 가짜 의존성(Fake*)."""
import pytest

from app.catalog import Place

# 2026-10-27 데이터 확장(574 → 3,444곳) 전 데이터. 특정 장소·"강서구에 카페 없음"(QA-9) 같은 대화 시나리오를 고정한
# 테스트는 이 파일로 돈다(로직 검증용). 새 데이터 자체는 tests/test_catalog.py 의 test_new_data_* 와 통합 테스트가 본다.
CATALOG_574 = "tests/fixtures/seoul_tour_574.json"


def _p(id, title, ct, category, cat3, addr, lat, lng, gu, tel="", image=""):
    kind = "food" if ct == "39" else ("event" if ct == "15" else "tour")
    return Place(id=id, title=title, content_type=ct, kind=kind, category=category, cat3=cat3,
                 addr=addr, tel=tel, lat=lat, lng=lng, image=image, gu=gu)


SMALL_PLACES = [
    _p("126512", "광화문", "12", "역사관광지", "A02010300", "서울특별시 종로구 사직로 161", 37.5760726, 126.9768042, "종로구"),
    _p("775394", "광화문광장", "12", "휴양관광지", "A02020700", "서울특별시 종로구 세종대로 172", 37.5727035, 126.9769710, "종로구"),
    _p("2733967", "가회동성당", "12", "역사관광지", "A02010900", "서울특별시 종로구 북촌로 57 (가회동)", 37.5820859, 126.9846617, "종로구", tel="02-763-1570"),
    _p("398373", "개성만두 궁", "39", "한식", "A05020100", "서울특별시 종로구 인사동10길 11-3 (관훈동)", 37.5743229, 126.9854257, "종로구"),
    _p("2543919", "광화문 세종클럽", "39", "이색음식점", "A05020700", "서울특별시 종로구 새문안로5가길 7 (내수동)", 37.5728257, 126.9740518, "종로구"),
    _p("2622715", "감꽃당", "39", "카페/전통찻집", "A05020900", "서울특별시 종로구 돈화문로11다길 38", 37.5738480, 126.9900725, "종로구"),
    _p("2895236", "구펠", "39", "카페/전통찻집", "A05020900", "서울특별시 성동구 왕십리로14길 30-1 (성수동1가)", 37.5484131, 127.0470125, "성동구"),
    _p("9999999", "도심속 바다축제", "15", "축제", "A02070200", "서울특별시 동작구 노들로 688 (노량진동)", 0.0, 0.0, "동작구"),
]


@pytest.fixture
def small_catalog():
    return {p.id: p for p in SMALL_PLACES}


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def encode(self, text):
        self.calls.append(text)
        return [0.0] * 768


class FakeSearcher:
    """카탈로그에서 type/cat3 조건에 맞는 장소를 카탈로그 순서대로(점수 내림차순) 돌려준다.

    scores: {place_id: score}를 주면 그 점수로 정렬. fail=True면 SearchUnavailable.
    """

    def __init__(self, catalog, scores=None, fail=False):
        self.catalog = catalog
        self.scores = scores or {}
        self.fail = fail
        self.calls = []

    def knn(self, vector, content_types, cat3, k):
        from app.search import SearchUnavailable

        self.calls.append({"content_types": set(content_types), "cat3": cat3, "k": k})
        if self.fail:
            raise SearchUnavailable("가짜 검색 서버 꺼짐")
        hits = []
        n = len(self.catalog)
        for i, p in enumerate(self.catalog.values()):
            if p.content_type not in content_types:
                continue
            if cat3 and p.cat3 != cat3:
                continue
            hits.append((p.id, self.scores.get(p.id, 1.0 - i / (n + 1))))
        hits.sort(key=lambda h: -h[1])
        return hits[:k]

    def ping(self):
        return not self.fail


class FakeLLM:
    def __init__(self, answer="가짜 답변이에요.", fail=False):
        self.answer = answer
        self.fail = fail
        self.prompts = []

    def generate(self, prompt):
        from app.llm import LLMUnavailable

        self.prompts.append(prompt)
        if self.fail:
            raise LLMUnavailable("가짜 LLM 꺼짐")
        return self.answer

    def ping(self):
        return not self.fail


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()
