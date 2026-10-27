"""관광공사 areaBasedList2 로 서울(lDongRegnCd=11) 장소 목록을 받아 data/raw/seoul_list.json 에 저장한다 (이어하기 가능).

    python scripts/fetch_list.py
    python scripts/fetch_list.py --max-calls 3

종류: 관광지 12, 문화시설 14, 레포츠 28, 음식점 39, 쇼핑 38, 축제·행사 15 (숙박 32는 받지 않음).
결과 형식: {"types": {"12": {"total": N, "next_page": p, "done": bool}}, "items": {contentid: item},
"calls": {"YYYY-MM-DD": 호출 수}}. 한 페이지마다 저장하므로 끊겨도 다시 실행하면 받은 페이지는 건너뛴다.
원본 data/seoul_tour.json 은 수정하지 않는다.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.enrich_tel import BASE_URL, QuotaExceeded, _scrub, save_json  # noqa: E402

CONTENT_TYPES = ("12", "14", "28", "39", "38", "15")
SEOUL_LDONG = "11"
DEFAULT_OUT = ROOT / "data" / "raw" / "seoul_list.json"


def new_state() -> dict:
    return {"types": {}, "items": {}, "calls": {}}


def load_state(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        return new_state()
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    for key, value in new_state().items():
        state.setdefault(key, value)
    return state


def parse_page(data: dict) -> tuple[list[dict], int]:
    body = (data.get("response", {}) or {}).get("body", {}) or {}
    items = body.get("items") or {}
    item = items.get("item") if isinstance(items, dict) else None
    if isinstance(item, dict):
        item = [item]
    try:
        total = int(body.get("totalCount") or 0)
    except (TypeError, ValueError):
        total = 0
    return list(item or []), total


def fetch_page(api_key: str, content_type: str, page: int, rows: int) -> tuple[list[dict], int]:
    import requests

    query = {
        "serviceKey": api_key, "MobileOS": "ETC", "MobileApp": "seoul-tour-chatbot", "_type": "json",
        "lDongRegnCd": SEOUL_LDONG, "contentTypeId": content_type,
        "numOfRows": rows, "pageNo": page, "arrange": "C",
    }
    resp = requests.get(f"{BASE_URL}/areaBasedList2", params=query, timeout=30)
    text = resp.text
    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in text or resp.status_code == 429:
        raise QuotaExceeded(text[:200])
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"JSON이 아닌 응답: {text[:200]}") from e
    return parse_page(data)


def fetch_all(state: dict, api_key: str, out: Path, rows: int = 1000, types=CONTENT_TYPES,
              fetch=fetch_page, max_calls: int | None = None, sleep: float = 0.0) -> dict:
    """종류별로 끝날 때까지 페이지를 넘겨 받는다. 한 페이지마다 저장. QuotaExceeded 는 저장 뒤 그대로 올린다."""
    made = 0
    for ctype in types:
        info = state["types"].setdefault(ctype, {"total": None, "next_page": 1, "done": False})
        while not info["done"]:
            if max_calls is not None and made >= max_calls:
                return state
            items, total = fetch(api_key, ctype, info["next_page"], rows)
            made += 1
            today = dt.date.today().isoformat()
            state["calls"][today] = state["calls"].get(today, 0) + 1
            for item in items:
                state["items"][str(item["contentid"])] = item
            info["total"] = total
            info["next_page"] += 1
            # 빈 페이지거나 전체 수만큼 넘겼으면 끝 (받는 도중 전체 수가 바뀌어도 멈춘다)
            info["done"] = not items or (info["next_page"] - 1) * rows >= total
            save_json(out, state)
            print(f"[{ctype}] {info['next_page'] - 1}페이지 {len(items)}건 (전체 {total})", flush=True)
            if sleep:
                time.sleep(sleep)
    return state


def main(argv=None) -> int:
    from app.config import ConfigError, load_settings

    parser = argparse.ArgumentParser(description="관광공사 서울 장소 목록(areaBasedList2) 받기")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--rows", type=int, default=1000, help="한 페이지 건수")
    parser.add_argument("--max-calls", type=int, default=None, help="이번 실행 최대 호출 수")
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args(argv)

    try:
        settings = load_settings(required=("TOUR_API_KEY",))
    except ConfigError as e:
        print(e)
        return 1
    key = settings.tour_api_key

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    state = load_state(out)
    try:
        fetch_all(state, key, out, rows=args.rows, max_calls=args.max_calls, sleep=args.sleep)
    except QuotaExceeded as e:
        print(f"일일 호출 한도 초과로 중단합니다. 내일 다시 실행하면 이어집니다. ({_scrub(e, key)})")
    except Exception as e:  # 받은 페이지까지는 저장돼 있다
        print(f"실패: {_scrub(e, key)}")
        return 1

    by_type: dict[str, int] = {}
    for item in state["items"].values():
        by_type[str(item.get("contenttypeid"))] = by_type.get(str(item.get("contenttypeid")), 0) + 1
    for ctype in CONTENT_TYPES:
        info = state["types"].get(ctype, {})
        print(f"  {ctype}: {by_type.get(ctype, 0)}건 / 전체 {info.get('total')} {'완료' if info.get('done') else '미완'}")
    print(f"누적 {len(state['items'])}건, 호출 기록 {state['calls']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
