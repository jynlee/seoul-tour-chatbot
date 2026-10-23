"""관광공사 API로 전화번호를 보강해 data/seoul_tour_enriched.json 에 저장한다 (1회성, 이어하기 가능).

    python scripts/enrich_tel.py --limit 5
    python scripts/enrich_tel.py

결과 형식: {contentid: {"tel": "02-..."}}. 한 건마다 저장하므로 중간에 끊겨도 다시 실행하면
이미 있는 건은 건너뛴다. 원본 data/seoul_tour.json 은 수정하지 않는다.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
INTRO_TEL_FIELDS = (
    "infocenterfood",
    "infocenter",
    "infocenterculture",
    "infocentershopping",
    "infocenterleports",
)
_TAG = re.compile(r"<[^>]+>")


def _clean(value) -> str:
    if not value:
        return ""
    text = _TAG.sub(" ", str(value))
    return " ".join(text.split())


def pick_tel(common: dict | None, intro: dict | None) -> str:
    tel = _clean((common or {}).get("tel"))
    if tel:
        return tel
    for field in INTRO_TEL_FIELDS:
        tel = _clean((intro or {}).get(field))
        if tel:
            return tel
    return ""


def save_json(path: Path, data: dict, retries: int = 5) -> None:
    """임시 파일에 쓴 뒤 교체(중간에 끊겨도 파일이 깨지지 않음). Windows 파일 잠금이면 잠깐 쉬고 재시도."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    for attempt in range(retries):
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, path)
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


def _scrub(error, api_key: str) -> str:
    """오류 메시지(요청 URL 포함)에서 API 키를 가린다."""
    text = str(error)
    return text.replace(api_key, "***") if api_key else text


class QuotaExceeded(RuntimeError):
    pass


def _call(operation: str, api_key: str, **params) -> dict:
    import requests

    query = {
        "serviceKey": api_key,
        "MobileOS": "ETC",
        "MobileApp": "seoul-tour-chatbot",
        "_type": "json",
        **params,
    }
    resp = requests.get(f"{BASE_URL}/{operation}", params=query, timeout=15)
    text = resp.text
    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in text or resp.status_code == 429:
        raise QuotaExceeded(text[:200])
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"JSON이 아닌 응답: {text[:200]}") from e
    items = (data.get("response", {}).get("body", {}) or {}).get("items") or {}
    item = items.get("item") if isinstance(items, dict) else None
    if isinstance(item, list):
        return item[0] if item else {}
    return item or {}


def fetch_tel(api_key: str, content_id: str, content_type: str) -> str:
    common = _call("detailCommon2", api_key, contentId=content_id)
    tel = pick_tel(common, None)
    if tel:
        return tel
    intro = _call("detailIntro2", api_key, contentId=content_id, contentTypeId=content_type)
    return pick_tel(common, intro)


def main(argv=None) -> int:
    from app.catalog import load_enriched, load_raw_items
    from app.config import ConfigError, load_settings

    parser = argparse.ArgumentParser(description="관광공사 API 전화번호 보강")
    parser.add_argument("--limit", type=int, default=None, help="이번 실행에서 새로 받을 최대 건수")
    parser.add_argument("--raw", default=str(ROOT / "data" / "seoul_tour.json"))
    parser.add_argument("--out", default=str(ROOT / "data" / "seoul_tour_enriched.json"))
    parser.add_argument("--sleep", type=float, default=0.1)
    args = parser.parse_args(argv)

    try:
        settings = load_settings(required=("TOUR_API_KEY",))
    except ConfigError as e:
        print(e)
        return 1

    out = Path(args.out)
    enriched = load_enriched(out)
    items = load_raw_items(args.raw)
    done = 0
    failed = 0
    for item in items:
        cid = str(item["contentid"])
        if cid in enriched:
            continue
        if args.limit is not None and done >= args.limit:
            break
        try:
            tel = fetch_tel(settings.tour_api_key, cid, str(item["contenttypeid"]))
        except QuotaExceeded as e:
            print(f"일일 호출 한도 초과로 중단합니다. 내일 다시 실행하면 이어집니다. ({_scrub(e, settings.tour_api_key)})")
            break
        except Exception as e:  # 실패한 건은 저장하지 않아 다음 실행 때 다시 시도
            failed += 1
            print(f"실패 {cid} {item.get('title')}: {_scrub(e, settings.tour_api_key)}")
            continue
        enriched[cid] = {"tel": tel}
        save_json(out, enriched)
        done += 1
        print(f"[{len(enriched)}/{len(items)}] {item.get('title')}: {tel or '(없음)'}")
        time.sleep(args.sleep)

    filled = sum(1 for v in enriched.values() if v.get("tel"))
    print(f"이번 실행 {done}건 저장, 실패 {failed}건. 누적 {len(enriched)}/{len(items)}건, 전화번호 있음 {filled}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
