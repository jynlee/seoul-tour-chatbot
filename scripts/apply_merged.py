"""합친 목록·개요·상세(data/raw/*)를 앱 데이터 파일에 반영한다 (API 호출 없음, 여러 번 돌려도 같은 결과).

    python scripts/apply_merged.py

- data/seoul_tour.json : data/raw/seoul_merged.json 의 장소로 교체 (형식 response.body.items.item 그대로)
- data/seoul_tour_enriched.json : 합친 목록의 장소만 남기고, 기존 tel·detail 은 유지,
  detail 이 없으면 data/raw/detail.json 의 값, 개요는 data/raw/overview.json 의 값을 "overview" 로.
상세를 더 받은 뒤 다시 돌리면 새 detail 이 채워진다. 기존 detail 은 덮어쓰지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.enrich_tel import save_json  # noqa: E402


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
    save_json(Path(args.raw_out), merged)
    save_json(Path(args.enriched), enriched)

    n = len(items)
    count = {k: sum(1 for v in enriched.values() if v.get(k)) for k in ("tel", "detail", "overview")}
    print(f"장소 {n}곳 반영. 전화 {count['tel']}, 상세 {count['detail']}, 개요 있음 {count['overview']} "
          f"(개요 받은 곳 {sum(1 for v in enriched.values() if 'overview' in v)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
