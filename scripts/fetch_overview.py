"""관광공사 detailCommon2 로 합친 목록(data/raw/seoul_merged.json) 장소의 개요(overview)를 받는다 (이어하기 가능).

    python scripts/fetch_overview.py --limit 5
    python scripts/fetch_overview.py

결과: data/raw/overview.json = {"overview": {contentid: 개요}, "calls": {"YYYY-MM-DD": 호출 수}}.
순서는 설계 §4대로 관광지·문화시설 → 음식점 → 레포츠·축제·쇼핑. 한 건마다 저장하므로 끊기거나 일일 한도에
걸려도 다시 실행하면 받은 건은 건너뛴다(개요가 빈 곳도 ""로 저장해 다시 부르지 않음). 2단계에서
data/seoul_tour_enriched.json 의 "overview" 로 옮긴다.
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.enrich_tel import QuotaExceeded, _call, _scrub, save_json  # noqa: E402

PRIORITY = {"12": 0, "14": 0, "39": 1, "28": 2, "15": 3, "38": 4}
DEFAULT_LIST = ROOT / "data" / "raw" / "seoul_merged.json"
DEFAULT_OUT = ROOT / "data" / "raw" / "overview.json"

_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def clean_overview(value) -> str:
    if not value:
        return ""
    text = _TAG.sub(" ", _BR.sub(" ", str(value)))
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(text.split())


def new_state() -> dict:
    return {"overview": {}, "calls": {}}


def load_state(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        return new_state()
    state = json.loads(path.read_text(encoding="utf-8"))
    for key, value in new_state().items():
        state.setdefault(key, value)
    return state


def order_items(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: PRIORITY.get(str(i["contenttypeid"]), 9))


def fetch_overviews(items: list[dict], state: dict, api_key: str, out: Path, call=_call,
                    limit: int | None = None, sleep: float = 0.0) -> tuple[int, int]:
    """(이번에 저장한 수, 실패 수). QuotaExceeded 는 받은 데까지 저장된 상태로 그대로 올린다."""
    done = failed = 0
    for item in order_items(items):
        cid = str(item["contentid"])
        if cid in state["overview"]:
            continue
        if limit is not None and done >= limit:
            break
        today = dt.date.today().isoformat()
        state["calls"][today] = state["calls"].get(today, 0) + 1
        try:
            common = call("detailCommon2", api_key, contentId=cid)
        except QuotaExceeded:
            save_json(out, state)
            raise
        except Exception as e:  # 실패한 건은 저장하지 않아 다음 실행 때 다시 시도
            failed += 1
            print(f"실패 {cid} {item.get('title')}: {_scrub(e, api_key)}", flush=True)
            continue
        state["overview"][cid] = clean_overview(common.get("overview"))
        save_json(out, state)
        done += 1
        if done % 100 == 0:
            print(f"  이번 실행 {done}건 (누적 {len(state['overview'])})", flush=True)
        if sleep:
            time.sleep(sleep)
    return done, failed


def main(argv=None) -> int:
    from app.catalog import load_raw_items
    from app.config import ConfigError, load_settings

    parser = argparse.ArgumentParser(description="관광공사 개요(detailCommon2) 받기")
    parser.add_argument("--list", default=str(DEFAULT_LIST))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=None, help="이번 실행에서 새로 받을 최대 건수")
    parser.add_argument("--sleep", type=float, default=0.1)
    args = parser.parse_args(argv)

    try:
        settings = load_settings(required=("TOUR_API_KEY",))
    except ConfigError as e:
        print(e)
        return 1
    key = settings.tour_api_key

    items = load_raw_items(args.list)
    out = Path(args.out)
    state = load_state(out)
    done = failed = 0
    try:
        done, failed = fetch_overviews(items, state, key, out, limit=args.limit, sleep=args.sleep)
    except QuotaExceeded as e:
        print(f"일일 호출 한도 초과로 중단합니다. 내일 다시 실행하면 이어집니다. ({_scrub(e, key)})")

    ov = state["overview"]
    left: dict[str, int] = {}
    for i in items:
        if str(i["contentid"]) not in ov:
            left[str(i["contenttypeid"])] = left.get(str(i["contenttypeid"]), 0) + 1
    filled = sum(1 for v in ov.values() if v)
    print(f"이번 실행 저장 {done}건, 실패 {failed}건. 누적 {len(ov)}/{len(items)}건(개요 있음 {filled}), "
          f"남은 종류별 {left}, 날짜별 호출 {state['calls']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
