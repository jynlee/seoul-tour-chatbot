"""받은 서울 목록(data/raw/seoul_list.json)을 사용자 확정 기준(설계 §3)으로 걸러 합친 목록을 만든다 (API 호출 없음).

    python scripts/build_merged.py

결과:
- data/raw/seoul_merged.json : data/seoul_tour.json 과 같은 형식(response.body.items.item)
- data/raw/shopping_kept.tsv : 남긴 쇼핑 장소와 남긴 이유
기준: 쇼핑은 시장·백화점·면세점·거리/상가·쇼핑몰/아웃렛·공방/관광기념품 + 지정한 큰 쇼핑 장소,
음식점·카페는 체인을 거르지 않고 눈에 띄는 프랜차이즈만 개별 제외, 새 목록에 없는 기존 장소는 뺌,
같은 이름·50m 안 중복은 modifiedtime 최신 쪽만 남김. 원본 data/seoul_tour.json 은 수정하지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_list import TYPE_NAMES, find_duplicates, shopping_reason  # noqa: E402
from scripts.enrich_tel import save_json  # noqa: E402

TYPE_ORDER = ("12", "14", "39", "28", "15", "38")  # 개요 받는 순서와 같게
TAX_REFUND_LCLS = "SH040300"  # 사후면세점: 대부분 개별 매장 등록 건
CRAFT_LCLS = ("SH050100", "SH050300")  # 공방/공예품점, 관광기념품/특산물판매점
# 사용자 확정(2026-10-27): 규칙에서는 빠지지만 관광객이 갈 만한 큰 쇼핑 장소
SHOP_INCLUDE = frozenset({
    "센트럴시티", "고투몰(강남터미널 지하쇼핑몰)", "타임스퀘어", "가든파이브라이프(Garden5life)",
    "회현지하쇼핑센터", "용산전자랜드", "테크노마트 강변점", "청평화패션몰", "신평화패션타운",
    "밀리오레 동대문점", "가락몰", "엔터식스 왕십리역점", "케이팝 스퀘어 홍대", "카카오프렌즈 홍대 플래그십 스토어",
})
# 눈에 띄는 프랜차이즈 지점만 개별 제외 (음식점·카페 체인은 거르지 않음)
FOOD_EXCLUDE = frozenset({
    "메가MGC커피 관악구청점", "서부청기와감자탕 서울대입구역점", "쭈꾸미킹2.0 상봉점",
    "옛골토성 청계산점", "유닭스토리 닭한마리 신촌점",
})
DEFAULT_LIST = ROOT / "data" / "raw" / "seoul_list.json"
DEFAULT_OUT = ROOT / "data" / "raw" / "seoul_merged.json"
DEFAULT_SHOP_OUT = ROOT / "data" / "raw" / "shopping_kept.tsv"


def keep_reason(item: dict) -> str | None:
    """넣는 이유. None 이면 뺌."""
    ctype = str(item.get("contenttypeid"))
    title = item.get("title", "").strip()
    if ctype == "38":
        if title in SHOP_INCLUDE and item.get("lclsSystm3") != TAX_REFUND_LCLS:
            return "큰 쇼핑 장소(지정)"
        if item.get("lclsSystm3") in CRAFT_LCLS:
            return "공방·관광기념품"
        return shopping_reason(item)
    if ctype == "39":
        return None if title in FOOD_EXCLUDE else TYPE_NAMES[ctype]
    return TYPE_NAMES.get(ctype)


def dedupe(items: list[dict], meters: float = 50) -> tuple[list[dict], list[dict]]:
    """같은 이름·meters 안 중복은 modifiedtime 최신 쪽만 남긴다. (남긴 것, 뺀 것)"""
    drop: set[str] = set()
    for a, b in find_duplicates(items, meters=meters):
        older = a if (a.get("modifiedtime", ""), a["contentid"]) < (b.get("modifiedtime", ""), b["contentid"]) else b
        drop.add(older["contentid"])
    return [i for i in items if i["contentid"] not in drop], [i for i in items if i["contentid"] in drop]


def merge(items: dict[str, dict]) -> dict:
    """새 목록만 기준으로 거른다(새 목록에 없는 기존 장소는 자연히 빠짐)."""
    kept, dropped_by_rule = [], 0
    for item in items.values():
        if keep_reason(item):
            kept.append(item)
        else:
            dropped_by_rule += 1
    kept, dup = dedupe(kept)
    kept.sort(key=lambda i: (TYPE_ORDER.index(str(i["contenttypeid"])), i["contentid"]))
    shopping = [(i["contentid"], i["title"], keep_reason(i)) for i in kept if str(i["contenttypeid"]) == "38"]
    return {"items": kept, "dropped_by_rule": dropped_by_rule, "duplicates": dup, "shopping": shopping}


def main(argv=None) -> int:
    from app.catalog import load_raw_items

    parser = argparse.ArgumentParser(description="합친 서울 목록 만들기")
    parser.add_argument("--list", default=str(DEFAULT_LIST))
    parser.add_argument("--raw", default=str(ROOT / "data" / "seoul_tour.json"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--shop-out", default=str(DEFAULT_SHOP_OUT))
    args = parser.parse_args(argv)

    items = json.loads(Path(args.list).read_text(encoding="utf-8"))["items"]
    titles = {i["title"].strip() for i in items.values()}
    for name in sorted((SHOP_INCLUDE | FOOD_EXCLUDE) - titles):
        print(f"경고: 지정 목록의 '{name}'이(가) 새 목록에 없음")

    result = merge(items)
    kept = result["items"]
    save_json(Path(args.out), {"response": {"body": {"items": {"item": kept}, "totalCount": len(kept)}}})
    lines = ["contentid\ttitle\treason"] + [f"{c}\t{t}\t{r}" for c, t, r in result["shopping"]]
    Path(args.shop_out).write_text("\n".join(lines) + "\n", encoding="utf-8")

    old = {str(i["contentid"]) for i in load_raw_items(args.raw)}
    ids = {i["contentid"] for i in kept}
    print(f"합친 목록 {len(kept)}곳 (규칙으로 뺀 곳 {result['dropped_by_rule']}, 중복으로 뺀 곳 {len(result['duplicates'])}: "
          f"{', '.join(i['title'] + '(' + i['contentid'] + ')' for i in result['duplicates'])})")
    for t in TYPE_ORDER:
        print(f"  {t} {TYPE_NAMES[t]}: {sum(1 for i in kept if str(i['contenttypeid']) == t)}곳")
    reasons: dict[str, int] = {}
    for _c, _t, r in result["shopping"]:
        reasons[r] = reasons.get(r, 0) + 1
    print(f"  쇼핑 이유별: {reasons}")
    print(f"  기존 {len(old)}곳 중 남음 {len(old & ids)}, 빠짐 {len(old - ids)} (새 목록에 없음 {len(old - set(items))})")
    print(f"  새로 들어온 곳 {len(ids - old)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
