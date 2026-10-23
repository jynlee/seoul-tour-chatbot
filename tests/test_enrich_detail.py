import json

from app.catalog import load_catalog
from scripts.enrich_detail import clean_value, pick_detail


def test_clean_value_br_and_tags():
    assert clean_value("[평일]<br>- 11:30~21:30<br />- 준비시간 15:00~16:00") == "[평일] / - 11:30~21:30 / - 준비시간 15:00~16:00"
    assert clean_value("<b>가능</b> ") == "가능"
    assert clean_value("") == ""
    assert clean_value(None) == ""
    assert clean_value("0") == ""  # 관광공사 '없음' 표기


def test_pick_detail_food():
    intro = {"contenttypeid": "39", "firstmenu": "고기만두전골", "treatmenu": "김치만두전골 / 만두국",
             "infocenterfood": "02-733-9240", "parkingfood": "불가능",
             "opentimefood": "11:30~21:30<br>마지막 주문 20:50", "restdatefood": "연중무휴",
             "reservationfood": "", "lcnsno": "123", "kidsfacility": "0"}
    d = pick_detail("39", intro)
    assert d == {
        "parking": "불가능",
        "hours": "11:30~21:30 / 마지막 주문 20:50",
        "rest_day": "연중무휴",
        "menu": "고기만두전골 / 김치만두전골 / 만두국",
        "contact": "02-733-9240",
    }


def test_pick_detail_tour_and_culture():
    d = pick_detail("12", {"parking": "가능 (약 240대)", "usetime": "09:00~18:00", "restdate": "매주 화요일",
                           "chkpet": "불가", "chkbabycarriage": "없음", "infocenter": "02-3700-3901"})
    assert d["parking"] == "가능 (약 240대)"
    assert d["pet"] == "불가"
    assert d["stroller"] == "없음"
    c = pick_detail("14", {"parkingculture": "가능", "parkingfee": "무료", "usefee": "성인 3,000원"})
    assert c["parking"] == "가능 (주차요금: 무료)"
    assert c["fee"] == "성인 3,000원"


def test_pick_detail_event():
    d = pick_detail("15", {"eventstartdate": "20251212", "eventenddate": "20251231", "playtime": "17:30~22:00",
                           "usetimefestival": "무료", "eventplace": "광화문 광장 일대", "sponsor1tel": "02-337-3692"})
    assert d["period"] == "2025.12.12 ~ 2025.12.31"
    assert d["hours"] == "17:30~22:00"
    assert d["fee"] == "무료"
    assert d["place"] == "광화문 광장 일대"
    assert d["contact"] == "02-337-3692"


def test_catalog_loads_detail(tmp_path):
    enriched = tmp_path / "e.json"
    enriched.write_text(json.dumps({"398373": {"tel": "02-1", "detail": {"parking": "불가능"}}}), encoding="utf-8")
    catalog = load_catalog("data/seoul_tour.json", enriched)
    assert catalog["398373"].detail == {"parking": "불가능"}
    assert catalog["126512"].detail == {}
