"""받은 서울 목록(data/raw/seoul_list.json)의 분포를 뽑는다 — 쇼핑 거르기·체인 후보·중복·짧은 제목 (API 호출 없음).

    python scripts/analyze_list.py

리드·사용자가 거르기 기준을 정하기 위한 보고용. 어떤 파일도 바꾸지 않는다.
"""
import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog import SEOUL_BOUNDS, load_raw_items  # noqa: E402
from app.center import title_aliases  # noqa: E402

CAFE_CAT3 = "A05020900"
CAFE_LCLS = ("FD050100", "FD050200")  # 카페, 찻집
TYPE_NAMES = {"12": "관광지", "14": "문화시설", "15": "축제·행사", "28": "레포츠", "38": "쇼핑", "39": "음식점"}

# 쇼핑 남기는 이유: 신분류(lclsSystm3) → 구분류(cat3) → 제목 순
SHOP_LCLS = {
    "SH010100": "백화점",
    "SH060100": "시장", "SH060200": "시장",
    "SH040100": "면세점(시내·공항)", "SH040200": "면세점(시내·공항)",
    "SH020100": "쇼핑몰·아웃렛", "SH020200": "쇼핑몰·아웃렛",
}
SHOP_CAT3 = {"A04010100": "시장", "A04010200": "시장", "A04010300": "백화점", "A04010400": "면세점(시내·공항)"}
STREET_WORDS = ("거리", "골목", "상가", "시장")

_PAREN = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_INNER = re.compile(r"[\(\[]([^\)\]]*)[\)\]]")


def _base(title: str) -> str:
    return " ".join(_PAREN.sub(" ", title).split())


def branch_suffix(title: str) -> str | None:
    """'○○점' 지점명: 괄호 안이 '…점'이거나, 두 단어 이상일 때 마지막 단어가 '…점'."""
    for inner in _INNER.findall(title):
        inner = inner.strip()
        if inner.endswith("점") and len(inner) >= 2:
            return inner
    words = _base(title).split()
    if len(words) >= 2 and words[-1].endswith("점") and len(words[-1]) >= 2:
        return words[-1]
    return None


def chain_base(title: str) -> str:
    """지점명·괄호를 뗀 상호(공백 없애고 소문자)."""
    words = _base(title).split()
    if len(words) >= 2 and words[-1].endswith("점") and len(words[-1]) >= 2:
        words = words[:-1]
    return "".join(words).lower()


def shopping_reason(item: dict) -> str | None:
    """설계 §3 출발점으로 남길 이유. None 이면 빠짐(사후면세점 개별 매장·전문매장 등)."""
    reason = SHOP_LCLS.get(item.get("lclsSystm3", "")) or SHOP_CAT3.get(item.get("cat3", ""))
    if reason:
        return reason
    words = _base(item.get("title", "")).split()
    if branch_suffix(item.get("title", "")) and len(words) >= 2 and words[-1].endswith("점"):
        words = words[:-1]  # '올리브영 명동거리점'의 지점명은 보지 않음
    name = " ".join(words)
    if any(w in name for w in STREET_WORDS) and not name.endswith("약국"):
        return "거리·골목·상가·시장(제목)"
    return None


def is_cafe(item: dict) -> bool:
    return item.get("cat3") == CAFE_CAT3 or item.get("lclsSystm3", "") in CAFE_LCLS


def _float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _meters(a: dict, b: dict) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (_float(a.get("mapy")), _float(a.get("mapx")),
                                                _float(b.get("mapy")), _float(b.get("mapx"))))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def find_duplicates(items: list[dict], meters: float = 50) -> list[tuple[dict, dict]]:
    """같은 이름(공백 무시)·meters 안·다른 id 인 쌍."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_name["".join(item.get("title", "").split()).lower()].append(item)
    pairs = []
    for group in by_name.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a["contentid"] != b["contentid"] and _meters(a, b) <= meters:
                    pairs.append((a, b))
    return pairs


def short_titles(items: list[dict], max_len: int = 2) -> list[dict]:
    """부르는 이름(괄호 뺀 이름 등) 중 공백 빼고 max_len 글자 이하가 있는 장소."""
    return [i for i in items if any(len(a.replace(" ", "")) <= max_len for a in title_aliases(i.get("title", "")))]


def has_coords(item: dict) -> bool:
    min_lat, max_lat, min_lng, max_lng = SEOUL_BOUNDS
    lat, lng = _float(item.get("mapy")), _float(item.get("mapx"))
    return bool(lat) and bool(lng) and min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


def _chains(items: list[dict], top: int) -> None:
    groups: dict[str, list[str]] = defaultdict(list)
    for i in items:
        groups[chain_base(i["title"])].append(i["title"])
    multi = {k: v for k, v in groups.items() if len(v) >= 2}
    suffix = [i["title"] for i in items if branch_suffix(i["title"])]
    either = {i["contentid"] for i in items if branch_suffix(i["title"]) or len(groups[chain_base(i["title"])]) >= 2}
    print(f"  같은 상호 2곳 이상: 상호 {len(multi)}개, 장소 {sum(len(v) for v in multi.values())}곳")
    print(f"  '○○점'으로 끝나는 이름: {len(suffix)}곳 (둘 중 하나라도 해당: {len(either)}곳 / {len(items)}곳)")
    for k, v in sorted(multi.items(), key=lambda x: (-len(x[1]), x[0]))[:top]:
        print(f"    {len(v)}곳 {k}: {', '.join(v[:4])}{' …' if len(v) > 4 else ''}")
    lone = [t for t in suffix if len(groups[chain_base(t)]) < 2]
    print(f"  '○○점'인데 같은 상호가 1곳뿐인 예({len(lone)}곳): {', '.join(lone[:15])}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="서울 목록 분포 보고")
    parser.add_argument("--list", default=str(ROOT / "data" / "raw" / "seoul_list.json"))
    parser.add_argument("--raw", default=str(ROOT / "data" / "seoul_tour.json"))
    parser.add_argument("--codes", default=str(ROOT / "data" / "raw" / "lcls_codes.json"))
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args(argv)

    state = json.loads(Path(args.list).read_text(encoding="utf-8"))
    codes = json.loads(Path(args.codes).read_text(encoding="utf-8")) if Path(args.codes).exists() else {}
    items = list(state["items"].values())
    old = {str(i["contentid"]): i for i in load_raw_items(args.raw)}
    ids = set(state["items"])

    print("## 종류별")
    for t, name in TYPE_NAMES.items():
        group = [i for i in items if i["contenttypeid"] == t]
        no_xy = [i for i in group if not has_coords(i)]
        no_cat = sum(1 for i in group if not i.get("cat3"))
        print(f"  {t} {name}: {len(group)}곳, 좌표 없음·서울 밖 {len(no_xy)}곳, cat3 빈 곳 {no_cat}곳"
              f"{' — ' + ', '.join(x['title'] for x in no_xy[:5]) if no_xy else ''}")
    print(f"  합계 {len(items)}곳, 호출 기록 {state.get('calls')}")
    print(f"  기존 {len(old)}곳 중 새 목록과 id 겹침 {len(ids & set(old))}곳, 새 목록에 없음 {len(set(old) - ids)}곳"
          f"{': ' + ', '.join(old[c]['title'] for c in sorted(set(old) - ids)) if set(old) - ids else ''}")

    changed = [f"{i['title']}({i['contenttypeid']}→{state['items'][c]['contenttypeid']})" for c, i in old.items()
               if c in ids and state["items"][c]["contenttypeid"] != i["contenttypeid"]]
    print(f"  기존과 종류(contenttypeid)가 바뀐 곳 {len(changed)}곳: {', '.join(changed)}")

    print("\n## 쇼핑 신분류(lclsSystm3)별 — 수와 예시 5개")
    shops = [i for i in items if i["contenttypeid"] == "38"]
    by_lcls: dict[str, list[dict]] = defaultdict(list)
    for i in shops:
        by_lcls[i.get("lclsSystm3", "")].append(i)
    for code, group in sorted(by_lcls.items(), key=lambda x: -len(x[1])):
        print(f"  {code} {codes.get(code, '?')}: {len(group)}곳 — {', '.join(i['title'] for i in group[:5])}")
    print("  (구분류 cat3 있는 쇼핑) " + str(Counter(i.get("cat3") for i in shops if i.get("cat3"))))
    pharm = sum(1 for i in by_lcls.get("SH040300", []) if "약국" in i["title"])
    print(f"  SH040300 사후면세점 중 제목에 '약국' {pharm}곳")

    print("\n## 쇼핑 거르기(설계 §3 출발점)")
    reasons = Counter(shopping_reason(i) for i in shops)
    for r, n in reasons.most_common():
        print(f"  {r or '빠짐'}: {n}곳")
    for r in ("거리·골목·상가·시장(제목)", "쇼핑몰·아웃렛"):
        print(f"  [{r}] 전부: {', '.join(i['title'] for i in shops if shopping_reason(i) == r)}")
    dropped = defaultdict(list)
    for i in shops:
        if not shopping_reason(i):
            dropped[i.get("lclsSystm3", "")].append(i["title"])
    for code, titles in sorted(dropped.items(), key=lambda x: -len(x[1])):
        sample = [t for t in titles if "약국" not in t][:12]
        print(f"  빠짐 {code} {codes.get(code, '?')} {len(titles)}곳 예: {', '.join(sample)}")
    old_shops = [i for i in old.values() if i["contenttypeid"] == "38"]
    gone = [i["title"] for i in old_shops if str(i["contentid"]) not in ids]
    old_drop = [state["items"][str(i["contentid"])] for i in old_shops if str(i["contentid"]) in ids]
    old_drop = [f"{i['title']}({i.get('lclsSystm3')})" for i in old_drop
                if i["contenttypeid"] == "38" and not shopping_reason(i)]  # 종류가 바뀐 곳(쇼핑→관광지)은 남음
    print(f"  기존 쇼핑 {len(old_shops)}곳 중 규칙으로 빠질 곳 {len(old_drop)}곳: {', '.join(old_drop)}")
    print(f"  기존 쇼핑 중 새 목록에 아예 없는 곳 {len(gone)}곳: {', '.join(gone)}")

    print("\n## 음식점 체인 후보 (카페 포함 전체)")
    food = [i for i in items if i["contenttypeid"] == "39"]
    _chains(food, args.top)
    print("\n## 카페(cat3 A05020900 또는 신분류 카페·찻집)만")
    cafes = [i for i in food if is_cafe(i)]
    print(f"  카페 {len(cafes)}곳 (cat3 카페 {sum(1 for i in food if i.get('cat3') == CAFE_CAT3)}곳)")
    _chains(cafes, args.top)
    print("  음식점 신분류별: " + ", ".join(f"{c} {codes.get(c, '?')} {n}"
                                         for c, n in Counter(i.get("lclsSystm3") for i in food).most_common()))

    print("\n## 같은 이름·50m 안·다른 id (쇼핑은 거른 뒤 기준)")
    kept = [i for i in items if i["contenttypeid"] != "38" or shopping_reason(i)]
    pairs = find_duplicates(kept, meters=50)
    print(f"  {len(pairs)}쌍: " + "; ".join(f"{a['title']}({a['contentid']}/{a['contenttypeid']}) = "
                                         f"{b['contentid']}/{b['contenttypeid']}" for a, b in pairs))
    same_name = defaultdict(list)
    for i in kept:
        same_name["".join(i["title"].split()).lower()].append(i)
    far = {k: v for k, v in same_name.items() if len(v) >= 2}
    print(f"  (참고) 같은 이름 2곳 이상(거리 무관) {len(far)}개 이름")

    print("\n## 짧은 이름(2글자 이하, 쇼핑 거른 뒤)")
    shorts = short_titles(kept, max_len=2)
    print(f"  {len(shorts)}곳: " + ", ".join(f"{i['title']}({TYPE_NAMES[i['contenttypeid']]})" for i in shorts))
    three = [i for i in kept if any(len(a.replace(" ", "")) == 3 for a in title_aliases(i["title"]))]
    print(f"  (참고) 3글자 이름 {len(three)}곳 — 2글자 규칙이 적용되지 않음")

    print("\n## 호출 예상 (쇼핑 거른 뒤, 체인은 거르지 않은 경우)")
    new_ids = {i["contentid"] for i in kept} - set(old)
    keep_old = [c for c in old if c not in state["items"] or c in {i["contentid"] for i in kept}]
    print(f"  남는 장소 {len(kept)}곳 (새 {len(new_ids)}곳 + 기존과 겹침 {len(kept) - len(new_ids)}곳)")
    print(f"  개요(detailCommon2): {len(kept)}건, 상세(detailIntro2): 새 장소 {len(new_ids)}건 → 합계 {len(kept) + len(new_ids)}건")
    print(f"  (기존 중 남는 곳 {len(keep_old)}곳은 상세가 이미 있음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
