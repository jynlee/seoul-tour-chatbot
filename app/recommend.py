"""후보 검색 결과 → 최종 추천 장소. 장소 목록은 항상 카탈로그에서 만든다."""
from dataclasses import dataclass

from app.catalog import Place, has_coords
from app.center import Center
from app.geo import haversine_m, walk_min
from app.intent import Intent
from app.schemas import PlaceOut

CANDIDATES_K = 100
MIN_PLACES = 3


@dataclass
class Recommendation:
    places: list[PlaceOut]
    fallback_note: str | None = None


def to_place_out(p: Place, distance_m: float | None = None) -> PlaceOut:
    return PlaceOut(
        id=p.id, title=p.title, kind="food" if p.kind == "food" else "tour",
        category=p.category, addr=p.addr, tel=p.tel, lat=p.lat, lng=p.lng, image=p.image,
        distance_m=None if distance_m is None else int(round(distance_m)),
        walk_min=None if distance_m is None else walk_min(distance_m),
    )


def _matches(p: Place, intent: Intent) -> bool:
    return p.content_type in intent.content_types and (not intent.cat3 or p.cat3 == intent.cat3)


def recommend(message: str, intent: Intent, center: Center | None, searcher, embedder,
              catalog: dict[str, Place], k: int = 5, radius_m: float = 1500) -> Recommendation:
    vector = embedder.encode(message)
    hits = searcher.knn(vector, intent.content_types, intent.cat3, CANDIDATES_K)

    candidates: list[Place] = []
    seen = set()
    for pid, _score in hits:  # 점수 내림차순
        p = catalog.get(pid)
        if p is None or pid in seen or not has_coords(p) or not _matches(p, intent):
            continue
        seen.add(pid)
        candidates.append(p)

    if center is None:
        return Recommendation(places=[to_place_out(p) for p in candidates[:k]])

    def dist(p: Place) -> float:
        return haversine_m(center.lat, center.lng, p.lat, p.lng)

    within = [(p, dist(p)) for p in candidates if dist(p) <= radius_m][:k]
    if within:
        if len(within) < MIN_PLACES:
            # 반경 안이 1~2곳이면 같은 조건의 가장 가까운 곳으로 3곳까지 채운다 (거리·도보 시간은 그대로 보여줌)
            chosen = {p.id for p, _ in within}
            extra = sorted(((p, dist(p)) for p in catalog.values()
                            if p.id not in chosen and has_coords(p) and _matches(p, intent)),
                           key=lambda x: x[1])
            within += extra[: MIN_PLACES - len(within)]
        within.sort(key=lambda x: x[1])
        return Recommendation(places=[to_place_out(p, d) for p, d in within])

    # 반경 안에 하나도 없으면: 카탈로그 전체에서 같은 조건의 가장 가까운 3곳
    nearest = sorted(((p, dist(p)) for p in catalog.values() if has_coords(p) and _matches(p, intent)),
                     key=lambda x: x[1])[:MIN_PLACES]
    if not nearest:
        return Recommendation(places=[])
    first, d = nearest[0]
    note = f"가장 가까운 곳은 {d / 1000:.1f}km 떨어진 {first.title}예요"
    return Recommendation(places=[to_place_out(p, dd) for p, dd in nearest], fallback_note=note)
