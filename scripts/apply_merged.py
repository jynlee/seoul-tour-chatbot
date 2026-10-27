"""합친 목록·개요·상세(data/raw/*)를 앱 데이터 파일에 반영한다 (API 호출 없음, 여러 번 돌려도 같은 결과).

    python scripts/apply_merged.py

- data/seoul_tour.json : data/raw/seoul_merged.json 의 장소로 교체 (형식 response.body.items.item 그대로)
- data/seoul_tour_enriched.json : 합친 목록의 장소만 남기고, 기존 tel·detail 은 유지,
  detail 이 없으면 data/raw/detail.json 의 값, 개요는 data/raw/overview.json 의 값을 "overview" 로.
상세를 더 받은 뒤 다시 돌리면 새 detail 이 채워진다. 기존 detail 은 덮어쓰지 않는다.
- 이름이 달라 합칠 때 안 걸린 중복('대원군별장(석파정)'·'석파정', 같은 좌표)은 여기서 하나만 남긴다(dedupe_by_alias).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.center import title_aliases  # noqa: E402
from scripts.analyze_list import _meters, has_coords  # noqa: E402
from scripts.enrich_tel import save_json  # noqa: E402

ALIAS_DUP_METERS = 50


def _read(path) -> dict:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_enriched(items: list[dict], old: dict, overview: dict[str, str], detail: dict) -> dict:
    out: dict[str, dict] = {}
    for item in items:
        cid = str(item["contentid"])
        entry = dict(old.get(cid, {}))
        if "detail" not in entry and "detail" in detail.get(cid, {}):
            entry["detail"] = detail[cid]["detail"]
        if cid in overview:
            entry["overview"] = overview[cid]
        out[cid] = entry
    return out


def _names(item: dict) -> set[str]:
    return {"".join(a.split()).lower() for a in title_aliases(item.get("title", ""))}


def _info(entry: dict) -> int:
    return len(entry.get("detail") or {}) + bool(entry.get("tel")) + bool(entry.get("overview"))


def dedupe_by_alias(items: list[dict], enriched: dict) -> tuple[list[dict], list[dict]]:
    """리드 결정(2026-10-27): 50m 안이고 한쪽 이름(제목·별칭)이 다른 쪽 이름과 같으면 하나만 —
    상세 정보(상세 항목·전화·개요)가 많은 쪽, 같으면 제목이 그 이름 그대로인 본체, 그다음 modifiedtime 최신. 순서는 유지."""
    by_name: dict[str, list[int]] = {}
    for x, item in enumerate(items):
        for name in _names(item):
            by_name.setdefault(name, []).append(x)
    pairs = sorted({(x, y) for xs in by_name.values() for i, x in enumerate(xs) for y in xs[i + 1:]})
    def rank(item: dict, shared: set[str]) -> tuple:
        named = "".join(item.get("title", "").split()).lower() in shared
        return _info(enriched.get(str(item["contentid"]), {})), named, str(item.get("modifiedtime", ""))

    dropped: set[str] = set()
    for x, y in pairs:
        a, b = items[x], items[y]
        ida, idb = str(a["contentid"]), str(b["contentid"])
        if (ida in dropped or idb in dropped or not (has_coords(a) and has_coords(b))
                or _meters(a, b) > ALIAS_DUP_METERS):
            continue
        shared = _names(a) & _names(b)
        dropped.add(idb if rank(a, shared) >= rank(b, shared) else ida)
    return ([i for i in items if str(i["contentid"]) not in dropped],
            [i for i in items if str(i["contentid"]) in dropped])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="합친 목록·개요·상세를 앱 데이터에 반영")
    parser.add_argument("--merged", default=str(ROOT / "data" / "raw" / "seoul_merged.json"))
    parser.add_argument("--overview", default=str(ROOT / "data" / "raw" / "overview.json"))
    parser.add_argument("--detail", default=str(ROOT / "data" / "raw" / "detail.json"))
    parser.add_argument("--raw-out", default=str(ROOT / "data" / "seoul_tour.json"))
    parser.add_argument("--enriched", default=str(ROOT / "data" / "seoul_tour_enriched.json"))
    args = parser.parse_args(argv)

    merged = _read(args.merged)
    items = merged["response"]["body"]["items"]["item"]
    enriched = build_enriched(items, _read(args.enriched), _read(args.overview).get("overview", {}), _read(args.detail))
    items, dups = dedupe_by_alias(items, enriched)
    enriched = {cid: v for cid, v in enriched.items() if cid in {str(i["contentid"]) for i in items}}
    merged["response"]["body"]["items"]["item"] = items
    merged["response"]["body"]["totalCount"] = len(items)
    if dups:
        print(f"이름(별칭)이 같은 50m 안 중복 {len(dups)}곳 뺌: " + ", ".join(f"{i['title']}({i['contentid']})" for i in dups))
    save_json(Path(args.raw_out), merged)
    save_json(Path(args.enriched), enriched)

    n = len(items)
    count = {k: sum(1 for v in enriched.values() if v.get(k)) for k in ("tel", "detail", "overview")}
    print(f"장소 {n}곳 반영. 전화 {count['tel']}, 상세 {count['detail']}, 개요 있음 {count['overview']} "
          f"(개요 받은 곳 {sum(1 for v in enriched.values() if 'overview' in v)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
