"""관광공사 detailIntro2 로 장소 상세 정보(주차·이용 시간·쉬는 날·메뉴·요금 등)를 보강한다 (1회성, 이어하기 가능).

    python scripts/enrich_detail.py --limit 5
    python scripts/enrich_detail.py

결과는 data/seoul_tour_enriched.json 의 각 장소에 "detail" 필드로 저장한다(기존 "tel"은 유지).
    {contentid: {"tel": "...", "detail": {"parking": "...", "hours": "...", ...}}}
한 건마다 저장하므로 중간에 끊겨도 다시 실행하면 detail 이 있는 건은 건너뛴다.
원본 data/seoul_tour.json 은 수정하지 않는다.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.enrich_tel import QuotaExceeded, _call, _scrub, save_json  # noqa: E402

# 사람이 실제로 묻는 항목만 공통 키로 모은다. 값: 타입별 detailIntro2 필드 (앞에서부터 이어 붙임)
DETAIL_FIELDS: dict[str, dict[str, tuple[str, ...]]] = {
    "12": {  # 관광지
        "parking": ("parking",), "hours": ("usetime",), "rest_day": ("restdate",),
        "season": ("useseason",), "pet": ("chkpet",), "stroller": ("chkbabycarriage",),
        "contact": ("infocenter",),
    },
    "14": {  # 문화시설
        "parking": ("parkingculture",), "hours": ("usetimeculture",), "rest_day": ("restdateculture",),
        "fee": ("usefee",), "discount": ("discountinfo",), "pet": ("chkpetculture",),
        "stroller": ("chkbabycarriageculture",), "contact": ("infocenterculture",),
    },
    "15": {  # 축제/행사
        "hours": ("playtime",), "fee": ("usetimefestival",), "place": ("eventplace",),
        "reservation": ("bookingplace",), "age": ("agelimit",), "contact": ("sponsor1tel",),
    },
    "28": {  # 레포츠
        "parking": ("parkingleports",), "hours": ("usetimeleports",), "rest_day": ("restdateleports",),
        "fee": ("usefeeleports",), "reservation": ("reservation",), "period": ("openperiod",),
        "pet": ("chkpetleports",), "stroller": ("chkbabycarriageleports",), "contact": ("infocenterleports",),
    },
    "38": {  # 쇼핑
        "parking": ("parkingshopping",), "hours": ("opentime",), "rest_day": ("restdateshopping",),
        "menu": ("saleitem",), "fee": ("saleitemcost",), "pet": ("chkpetshopping",),
        "stroller": ("chkbabycarriageshopping",), "contact": ("infocentershopping",),
    },
    "39": {  # 음식점
        "parking": ("parkingfood",), "hours": ("opentimefood",), "rest_day": ("restdatefood",),
        "menu": ("firstmenu", "treatmenu"), "reservation": ("reservationfood",),
        "packing": ("packing",), "contact": ("infocenterfood",),
    },
}
PARKING_FEE_FIELDS = ("parkingfee", "parkingfeeleports")

_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_EMPTY = {"", "0", "-"}


def clean_value(value) -> str:
    """HTML 태그 제거, <br>은 ' / '로, 공백 정리. 관광공사 '0'(없음)은 빈 값."""
    if value is None:
        return ""
    text = _BR.sub(" / ", str(value))
    text = _TAG.sub(" ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = " ".join(text.split())
    text = re.sub(r"(\s*/\s*)+", " / ", text).strip(" /")
    return "" if text in _EMPTY else text


def _fmt_date(yyyymmdd: str) -> str:
    v = clean_value(yyyymmdd)
    return f"{v[:4]}.{v[4:6]}.{v[6:8]}" if re.fullmatch(r"\d{8}", v) else v


def pick_detail(content_type: str, intro: dict | None) -> dict[str, str]:
    intro = intro or {}
    detail: dict[str, str] = {}
    for key, fields in DETAIL_FIELDS.get(str(content_type), {}).items():
        parts = []
        for f in fields:
            v = clean_value(intro.get(f))
            if v and v not in parts:
                parts.append(v)
        if parts:
            detail[key] = " / ".join(parts)
    if "parking" in detail:
        fee = next((clean_value(intro.get(f)) for f in PARKING_FEE_FIELDS if clean_value(intro.get(f))), "")
        if fee:
            detail["parking"] = f"{detail['parking']} (주차요금: {fee})"
    if str(content_type) == "15":
        start, end = _fmt_date(intro.get("eventstartdate")), _fmt_date(intro.get("eventenddate"))
        if start or end:
            detail["period"] = f"{start} ~ {end}".strip(" ~")
    return detail


def fetch_detail(api_key: str, content_id: str, content_type: str) -> dict[str, str]:
    intro = _call("detailIntro2", api_key, contentId=content_id, contentTypeId=content_type)
    return pick_detail(content_type, intro)


def main(argv=None) -> int:
    from app.catalog import load_enriched, load_raw_items
    from app.config import ConfigError, load_settings

    parser = argparse.ArgumentParser(description="관광공사 상세 정보(detailIntro2) 보강")
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
    key = settings.tour_api_key

    out = Path(args.out)
    enriched = load_enriched(out)
    items = load_raw_items(args.raw)
    done = failed = 0
    for item in items:
        cid = str(item["contentid"])
        entry = enriched.setdefault(cid, {})
        if "detail" in entry:
            continue
        if args.limit is not None and done >= args.limit:
            break
        try:
            entry["detail"] = fetch_detail(key, cid, str(item["contenttypeid"]))
        except QuotaExceeded as e:
            print(f"일일 호출 한도 초과로 중단합니다. 내일 다시 실행하면 이어집니다. ({_scrub(e, key)})")
            break
        except Exception as e:  # 실패한 건은 저장하지 않아 다음 실행 때 다시 시도
            failed += 1
            print(f"실패 {cid} {item.get('title')}: {_scrub(e, key)}", flush=True)
            continue
        save_json(out, enriched)
        done += 1
        print(f"[{done}] {item.get('title')}: {', '.join(entry['detail']) or '(없음)'}", flush=True)
        time.sleep(args.sleep)

    with_detail = [v.get("detail") for v in enriched.values() if "detail" in v]
    print(f"이번 실행 {done}건 저장, 실패 {failed}건. detail 누적 {len(with_detail)}/{len(items)}건")
    counts: dict[str, int] = {}
    for d in with_detail:
        for k in d:
            counts[k] = counts.get(k, 0) + 1
    for k, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {n}/{len(items)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
