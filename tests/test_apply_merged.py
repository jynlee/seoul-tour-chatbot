import json

from scripts.apply_merged import build_enriched, main


def _items(*ids):
    return [{"contentid": i, "contenttypeid": "12", "title": f"t{i}"} for i in ids]


def test_apply_merged_keeps_existing():
    old = {"1": {"tel": "02-1", "detail": {"parking": "가능"}}}
    detail = {"1": {"detail": {"parking": "새 값"}}, "2": {"detail": {"hours": "09:00"}}}
    overview = {"1": "궁궐", "2": "공원", "3": ""}
    out = build_enriched(_items("1", "2", "3"), old, overview, detail)
    assert out["1"] == {"tel": "02-1", "detail": {"parking": "가능"}, "overview": "궁궐"}  # 기존 상세 우선
    assert out["2"] == {"detail": {"hours": "09:00"}, "overview": "공원"}
    assert out["3"] == {"overview": ""}


def test_apply_merged_drops_missing_ids():
    out = build_enriched(_items("1"), {"9": {"tel": "02-9"}}, {}, {})
    assert out == {"1": {}}


def test_main_writes_same_format(tmp_path):
    merged = tmp_path / "merged.json"
    merged.write_text(json.dumps({"response": {"body": {"items": {"item": _items("1")}, "totalCount": 1}}}),
                      encoding="utf-8")
    old = tmp_path / "enriched.json"
    old.write_text(json.dumps({"1": {"tel": "02-1"}}), encoding="utf-8")
    raw_out = tmp_path / "seoul_tour.json"
    assert main(["--merged", str(merged), "--enriched", str(old), "--raw-out", str(raw_out),
                 "--overview", str(tmp_path / "none.json"), "--detail", str(tmp_path / "none2.json")]) == 0
    assert json.loads(raw_out.read_text(encoding="utf-8"))["response"]["body"]["items"]["item"][0]["contentid"] == "1"
    assert json.loads(old.read_text(encoding="utf-8")) == {"1": {"tel": "02-1"}}


def _place(cid, title, lat=37.5948, lng=126.9627, modified="20250101000000"):
    return {"contentid": cid, "contenttypeid": "12", "title": title, "mapy": str(lat), "mapx": str(lng),
            "modifiedtime": modified}


def test_dedupe_by_alias_keeps_richer_one():
    # 리드 결정: 50m 안이고 한쪽 별칭이 다른 쪽 제목·별칭과 같으면 하나만 (상세 정보가 많은 쪽, 같으면 수정일 최신)
    from scripts.apply_merged import dedupe_by_alias

    items = [_place("1", "대원군별장(석파정)"), _place("2", "석파정", modified="20260101000000"),
             _place("3", "석파정 서울미술관"), _place("4", "공근혜갤러리", lat=37.58, lng=126.98),
             _place("5", "[K드라마 촬영지] 공근혜갤러리", lat=37.58003, lng=126.98, modified="20260101000000"),
             _place("6", "석파정", lat=37.60, lng=126.96)]  # 같은 이름이어도 멀면 남김
    enriched = {"1": {"tel": "02-1", "detail": {"parking": "가능", "hours": "10:00"}}, "2": {"overview": "..."}}
    kept, dropped = dedupe_by_alias(items, enriched)
    assert [i["contentid"] for i in kept] == ["1", "3", "4", "6"]  # 4·5는 정보가 같아 제목이 그 이름인 본체(4)
    assert [i["contentid"] for i in dropped] == ["2", "5"]


def test_dedupe_by_alias_tie_keeps_place_named_exactly():
    # 정보가 같으면 제목이 그 이름 그대로인 본체 ('K-컬처 스크린(대한민국역사박물관)'이 더 최신이어도 박물관)
    from scripts.apply_merged import dedupe_by_alias

    items = [_place("1", "대한민국역사박물관"), _place("2", "K-컬처 스크린(대한민국역사박물관)", modified="20261022000000")]
    enriched = {"1": {"tel": "02", "detail": {"hours": "10:00"}}, "2": {"overview": "...", "detail": {"hours": "x"}}}
    kept, _dropped = dedupe_by_alias(items, enriched)
    assert [i["contentid"] for i in kept] == ["1"]


def test_main_applies_alias_dedupe(tmp_path):
    merged = tmp_path / "merged.json"
    merged.write_text(json.dumps({"response": {"body": {"items": {"item": [
        _place("1", "대원군별장(석파정)"), _place("2", "석파정")]}, "totalCount": 2}}}), encoding="utf-8")
    old = tmp_path / "enriched.json"
    old.write_text(json.dumps({"1": {"tel": "02-1"}}), encoding="utf-8")
    raw_out = tmp_path / "seoul_tour.json"
    main(["--merged", str(merged), "--enriched", str(old), "--raw-out", str(raw_out),
          "--overview", str(tmp_path / "none.json"), "--detail", str(tmp_path / "none2.json")])
    body = json.loads(raw_out.read_text(encoding="utf-8"))["response"]["body"]
    assert [i["contentid"] for i in body["items"]["item"]] == ["1"] and body["totalCount"] == 1
    assert json.loads(old.read_text(encoding="utf-8")) == {"1": {"tel": "02-1"}}
