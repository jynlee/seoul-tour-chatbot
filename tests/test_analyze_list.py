from scripts.analyze_list import branch_suffix, chain_base, find_duplicates, is_cafe, shopping_reason, short_titles


def _shop(title, lcls3="", cat3=""):
    return {"contentid": title, "contenttypeid": "38", "title": title, "lclsSystm3": lcls3, "cat3": cat3}


def test_chain_base():
    assert chain_base("스타벅스 명동점") == "스타벅스"
    assert chain_base("투썸플레이스(강남역점)") == "투썸플레이스"
    assert chain_base("햇빛촌순대국 본점") == "햇빛촌순대국"
    assert chain_base("광장시장") == "광장시장"
    assert chain_base("롯데백화점") == "롯데백화점"  # 한 단어 '○○점'은 상호 그대로
    assert chain_base("Paul Bassett 광화문점") == "paulbassett"


def test_branch_suffix():
    assert branch_suffix("스타벅스 명동점") == "명동점"
    assert branch_suffix("투썸플레이스(강남역점)") == "강남역점"
    assert branch_suffix("광장시장") is None
    assert branch_suffix("롯데백화점") is None


def test_shopping_reason():
    assert shopping_reason(_shop("신세계백화점 본점", "SH010100")) == "백화점"
    assert shopping_reason(_shop("망원시장", "SH060200")) == "시장"
    assert shopping_reason(_shop("논현 가구거리", "SH050200")) == "거리·골목·상가·시장(제목)"
    assert shopping_reason(_shop("롯데면세점 명동본점", "SH040200")) == "면세점(시내·공항)"
    assert shopping_reason(_shop("스타필드 코엑스몰", "SH020100")) == "쇼핑몰·아웃렛"
    assert shopping_reason(_shop("광장시장", "", "A04010200")) == "시장"  # 구분류만 있는 곳
    assert shopping_reason(_shop("메디원약국", "SH040300")) is None  # 사후면세점(개별 매장)
    assert shopping_reason(_shop("세실앤세드릭[면세점(TAX REFUND SHOP)]", "SH040300")) is None
    assert shopping_reason(_shop("금강제화 명동본점", "SH050200")) is None
    # 지점명에만 거리·시장이 든 체인 매장, 시장 안 약국은 빠짐
    assert shopping_reason(_shop("올리브영 명동거리점", "SH040300")) is None
    assert shopping_reason(_shop("다이소 수유시장2호점", "SH040300")) is None
    assert shopping_reason(_shop("망원시장약국", "SH040300")) is None
    assert shopping_reason(_shop("광장시장 365일장", "SH050200")) == "거리·골목·상가·시장(제목)"


def test_is_cafe():
    assert is_cafe({"cat3": "A05020900"})
    assert is_cafe({"cat3": "", "lclsSystm3": "FD050100"})
    assert is_cafe({"cat3": "", "lclsSystm3": "FD050200"})
    assert not is_cafe({"cat3": "A05020100", "lclsSystm3": "FD010100"})


def test_find_duplicates():
    items = [
        {"contentid": "1", "title": "경복궁", "mapy": "37.5796", "mapx": "126.9770"},
        {"contentid": "2", "title": "경복궁 ", "mapy": "37.5797", "mapx": "126.9771"},  # 약 14m
        {"contentid": "3", "title": "경복궁", "mapy": "37.6000", "mapx": "126.9770"},  # 2km 떨어짐
        {"contentid": "4", "title": "창덕궁", "mapy": "37.5796", "mapx": "126.9770"},
    ]
    pairs = find_duplicates(items, meters=50)
    assert [(a["contentid"], b["contentid"]) for a, b in pairs] == [("1", "2")]


def test_short_titles():
    items = [{"contentid": "1", "title": "그래픽"}, {"contentid": "2", "title": "갗"},
             {"contentid": "3", "title": "토인"}, {"contentid": "4", "title": "가회동성당"},
             {"contentid": "5", "title": "카페 (강남점)"}]
    assert [i["title"] for i in short_titles(items, max_len=2)] == ["갗", "토인", "카페 (강남점)"]
