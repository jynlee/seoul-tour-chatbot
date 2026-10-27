"""후보 검색 결과 → 최종 추천 장소. 장소 목록은 항상 카탈로그에서 만든다."""
import re
from dataclasses import dataclass, field

from app.catalog import Place, has_coords
from app.center import Center
from app.geo import SEOUL_GU, haversine_m, walk_min
from app.intent import Intent, matches_topic, title_has_topic_word, topic_words
from app.schemas import PlaceOut

CANDIDATES_K = 100
MIN_PLACES = 3
GROUP_RADIUS_M = 500

# 한 장소의 세부 장소('창덕궁 인정문'·'창덕궁 낙선재', '반포한강공원 달빛광장')는 제목 첫 단어가 같다 → 한 목록에 하나만.
_BRACKETS = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_COMMON_FIRST_WORDS = {"서울", "국립", "한국", "대한민국"}


def group_key(title: str) -> str | None:
    """세부 장소 묶음 이름: 괄호 뺀 제목의 첫 단어(끝의 '과/와'는 뗌). 흔한 앞말·한 글자는 None."""
    words = _BRACKETS.sub(" ", title).split()
    if not words:
        return None
    word = words[0]
    if len(word) > 3 and word[-1] in "과와":
        word = word[:-1]
    return None if len(word) < 2 or word in _COMMON_FIRST_WORDS else word


def one_per_group(places: list[Place], meters: float = GROUP_RADIUS_M) -> list[Place]:
    """앞선 장소와 묶음 이름이 같고 meters 안이면 뺀다(순서 유지). 멀리 떨어진 같은 앞말(지점 등)은 남긴다."""
    kept: list[Place] = []
    by_key: dict[str, list[Place]] = {}
    for p in places:
        key = group_key(p.title)
        if key and any(haversine_m(p.lat, p.lng, q.lat, q.lng) <= meters for q in by_key.get(key, [])):
            continue
        kept.append(p)
        if key:
            by_key.setdefault(key, []).append(p)
    return kept


@dataclass
class Recommendation:
    places: list[PlaceOut]
    fallback_note: str | None = None
    topic_missing: bool = False  # 세부 주제(산책 등)를 물었는데 맞는 곳이 하나도 없음 → 답변에서 솔직히 말함
    gu_wide: bool = False  # 구 기준점: 반경이 아니라 구 전체에서 골랐음 (거리·도보 null)
    gu_empty: bool = False  # 구 기준점인데 구 안에 맞는 곳이 0곳 → 가까운 다른 구에서 골랐음 (답변에서 솔직히)
    place_gus: dict[str, str] = field(default_factory=dict)  # 구 기준점 결과의 장소 id → 구 (다른 구인지 답에서 밝히게)


def to_place_out(p: Place, distance_m: float | None = None) -> PlaceOut:
    return PlaceOut(
        id=p.id, title=p.title, kind="food" if p.kind == "food" else "tour",
        category=p.category, addr=p.addr, tel=p.tel, lat=p.lat, lng=p.lng, image=p.image,
        distance_m=None if distance_m is None else int(round(distance_m)),
        walk_min=None if distance_m is None else walk_min(distance_m),
    )


def _matches(p: Place, intent: Intent) -> bool:
    return p.content_type in intent.content_types and (not intent.cat3 or p.cat3 == intent.cat3)


def _gu_of_center(center: Center | None) -> str | None:
    """구 기준점(또는 구를 이어받은 직전 기준점)이면 그 구 이름."""
    if center is None:
        return None
    if center.source == "gu" or (center.source == "history" and center.label in SEOUL_GU):
        return center.label
    return None


def recommend(message: str, intent: Intent, center: Center | None, searcher, embedder,
              catalog: dict[str, Place], k: int = 5, radius_m: float = 1500,
              exclude_ids: set[str] | frozenset = frozenset()) -> Recommendation:
    """exclude_ids: 이미 보여 준 장소("다른 데 더 추천해줘"). 기준점이 장소면 그 장소 자체도 뺀다.

    - 구 기준점: 반경 대신 그 구에 속한 곳 전체에서 관련도순 (구 중심 1.5km만 보면 구 전체를 대표하지 못함).
      거리·도보는 null.
    - 세부 주제(intent.topic)에 맞는 곳(분류·제목)은 앞으로 끌어올린다.
    """
    rec = _recommend(message, intent, center, searcher, embedder, catalog, k, radius_m, exclude_ids)
    if intent.topic and rec.places:
        rec.topic_missing = not any(matches_topic(p.category, p.title, intent.topic) for p in rec.places)
    return rec


def _recommend(message, intent, center, searcher, embedder, catalog, k, radius_m, exclude_ids) -> Recommendation:
    skip = set(exclude_ids)
    if center is not None and getattr(center, "place_id", None):
        skip.add(center.place_id)

    def ok(p: Place) -> bool:
        return p.id not in skip and has_coords(p) and _matches(p, intent)

    vector = embedder.encode(message)
    hits = searcher.knn(vector, intent.content_types, intent.cat3, CANDIDATES_K)

    candidates: list[Place] = []
    seen = set()
    for pid, _score in hits:  # 점수 내림차순
        p = catalog.get(pid)
        if p is None or pid in seen or not ok(p):
            continue
        seen.add(pid)
        candidates.append(p)

    # 세부 주제: 제목에 질문의 주제 말('궁'·'공원'·'야경')이 있으면 2, 주제 분류·제목 패턴이면 1 — 장소가 늘어
    # 같은 분류(종로구 역사관광지 등)가 많아지자 분류만으로는 경복궁·창덕궁이 뒤로 밀림
    words = topic_words(message, intent.topic)

    def boost(p: Place) -> int:
        return (2 if title_has_topic_word(p.title, words, intent.topic) else 0) +             (1 if matches_topic(p.category, p.title, intent.topic) else 0)

    candidates.sort(key=lambda p: -boost(p))  # 안정 정렬: 주제 맞는 곳 먼저, 그 안에서는 관련도순
    candidates = one_per_group(candidates)

    if center is None:
        return Recommendation(places=[to_place_out(p) for p in candidates[:k]])

    def dist(p: Place) -> float:
        return haversine_m(center.lat, center.lng, p.lat, p.lng)

    gu = _gu_of_center(center)
    if gu is not None:
        # kNN 상위 후보에 없던 같은 구 장소도 뒤에 붙인다 (구 안에서 빠지는 곳이 없게)
        # 구 이름과 같은 제목의 장소('강남')는 사용자가 말한 게 지역이므로 뺀다
        def in_this_gu(p: Place) -> bool:
            return p.gu == gu and p.title not in (gu, gu[:-1])

        in_gu = [p for p in candidates if in_this_gu(p)]
        in_gu += [p for p in catalog.values() if in_this_gu(p) and p.id not in seen and ok(p)]
        in_gu.sort(key=lambda p: -boost(p))
        in_gu = one_per_group(in_gu)
        chosen = in_gu[:k]
        if len(chosen) < MIN_PLACES:
            # 구 안이 0~2곳이면 같은 조건의 가장 가까운 다른 구 장소로 3곳까지 채운다
            ids = {p.id for p in chosen}
            extra = sorted((p for p in catalog.values() if p.id not in ids and ok(p)), key=dist)
            chosen = one_per_group(chosen + extra)[:MIN_PLACES]
        # 구 중심(평균 좌표)에서 잰 거리는 사용자에게 의미가 없어 distance_m·walk_min 은 null (QA-8, QA-9: 구 밖으로 채워도)
        return Recommendation(places=[to_place_out(p) for p in chosen], gu_wide=True, gu_empty=not in_gu,
                              place_gus={p.id: p.gu for p in chosen})

    within = [(p, dist(p)) for p in candidates if dist(p) <= radius_m][:k]
    if within:
        if len(within) < MIN_PLACES:
            # 반경 안이 1~2곳이면 같은 조건의 가장 가까운 곳으로 3곳까지 채운다 (거리·도보 시간은 그대로 보여줌)
            chosen = {p.id for p, _ in within}
            extra = sorted((p for p in catalog.values() if p.id not in chosen and ok(p)), key=dist)
            within = [(p, dist(p)) for p in one_per_group([p for p, _ in within] + extra)[:MIN_PLACES]]
        within.sort(key=lambda x: (-boost(x[0]), x[1]))  # 주제 맞는 곳 먼저, 그다음 가까운 순
        return Recommendation(places=[to_place_out(p, d) for p, d in within])

    # 반경 안에 하나도 없으면: 카탈로그 전체에서 같은 조건의 가장 가까운 3곳
    nearest = [(p, dist(p)) for p in one_per_group(sorted((p for p in catalog.values() if ok(p)), key=dist))[:MIN_PLACES]]
    if not nearest:
        return Recommendation(places=[])
    first, d = nearest[0]
    note = f"가장 가까운 곳은 {d / 1000:.1f}km 떨어진 {first.title}예요"
    return Recommendation(places=[to_place_out(p, dd) for p, dd in nearest], fallback_note=note)
