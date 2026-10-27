from scripts.build_merged import FOOD_EXCLUDE, SHOP_INCLUDE, dedupe, keep_reason, merge


def _item(cid, title, ctype="38", lcls3="", modified="20240101000000", y="37.5", x="127.0"):
    return {"contentid": cid, "contenttypeid": ctype, "title": title, "lclsSystm3": lcls3, "cat3": "",
            "modifiedtime": modified, "mapy": y, "mapx": x}


def test_keep_reason_shopping():
    assert keep_reason(_item("1", "망원시장", lcls3="SH060200")) == "시장"
    assert keep_reason(_item("2", "스타필드 코엑스몰", lcls3="SH020100")) == "쇼핑몰·아웃렛"
    assert keep_reason(_item("3", "한지추억", lcls3="SH050100")) == "공방·관광기념품"
    assert keep_reason(_item("4", "한국공예관", lcls3="SH050300")) == "공방·관광기념품"
    assert keep_reason(_item("5", "센트럴시티", lcls3="SH070100")) == "큰 쇼핑 장소(지정)"
    assert keep_reason(_item("6", "메디원약국", lcls3="SH040300")) is None
    # 같은 이름의 사후면세점 등록 건(개별 매장 기록)은 지정 장소로 보지 않음
    assert keep_reason(_item("8", "타임스퀘어", lcls3="SH040300")) is None
    assert keep_reason(_item("9", "타임스퀘어", lcls3="SH050200")) == "큰 쇼핑 장소(지정)"
    assert keep_reason(_item("7", "올리브영 명동거리점", lcls3="SH040300")) is None


def test_keep_reason_food_and_others():
    assert keep_reason(_item("1", "메가MGC커피 관악구청점", ctype="39", lcls3="FD050100")) is None
    assert keep_reason(_item("2", "햇빛촌순대국 본점", ctype="39")) == "음식점"
    assert keep_reason(_item("3", "경복궁", ctype="12")) == "관광지"
    assert keep_reason(_item("4", "롯데호텔", ctype="32")) is None  # 숙박은 넣지 않음


def test_include_and_exclude_lists_are_titles():
    assert "센트럴시티" in SHOP_INCLUDE and len(SHOP_INCLUDE) == 14
    assert "메가MGC커피 관악구청점" in FOOD_EXCLUDE


def test_dedupe_keeps_latest_modified():
    a = _item("1", "익선동 한옥거리", ctype="12", modified="20200101000000", y="37.5740", x="126.9890")
    b = _item("2", "익선동 한옥거리", ctype="12", modified="20250101000000", y="37.5741", x="126.9891")
    c = _item("3", "익선동 한옥거리", ctype="12", modified="20260101000000", y="37.6000", x="126.9890")  # 멀리
    kept, dropped = dedupe([a, b, c], meters=50)
    assert sorted(i["contentid"] for i in kept) == ["2", "3"]
    assert [i["contentid"] for i in dropped] == ["1"]


def test_merge_drops_old_missing_and_filters():
    items = {
        "1": _item("1", "망원시장", lcls3="SH060200"),
        "2": _item("2", "메디원약국", lcls3="SH040300"),
        "3": _item("3", "경복궁", ctype="12"),
    }
    result = merge(items)
    assert sorted(i["contentid"] for i in result["items"]) == ["1", "3"]
    assert result["dropped_by_rule"] == 1
    assert result["shopping"] == [("1", "망원시장", "시장")]
