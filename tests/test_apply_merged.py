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
