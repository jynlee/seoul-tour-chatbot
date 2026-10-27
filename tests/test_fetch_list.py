import json

import pytest

from scripts.enrich_tel import QuotaExceeded
from scripts.fetch_list import fetch_all, new_state, parse_page


def _resp(items, total):
    return {"response": {"body": {"items": {"item": items} if items is not None else "", "totalCount": total}}}


def test_parse_page_list():
    items, total = parse_page(_resp([{"contentid": "1"}, {"contentid": "2"}], 5))
    assert [i["contentid"] for i in items] == ["1", "2"]
    assert total == 5


def test_parse_page_single_and_empty():
    items, total = parse_page(_resp({"contentid": "1"}, 1))
    assert items == [{"contentid": "1"}] and total == 1
    assert parse_page(_resp(None, 0)) == ([], 0)
    assert parse_page({"response": {"body": {"items": {}, "totalCount": "3"}}}) == ([], 3)


def _fake_pages(pages: dict, quota_at=None, calls=None):
    """pages: {(type, page): ([ids], total)}"""
    def fetch(api_key, content_type, page, rows):
        if calls is not None:
            calls.append((content_type, page))
        if quota_at == (content_type, page):
            raise QuotaExceeded("LIMITED_NUMBER_OF_SERVICE_REQUESTS")
        ids, total = pages.get((content_type, page), ([], 0))
        return [{"contentid": i, "contenttypeid": content_type, "title": f"t{i}"} for i in ids], total
    return fetch


def test_fetch_type_until_empty_or_total(tmp_path):
    out = tmp_path / "list.json"
    pages = {("12", 1): (["a", "b"], 3), ("12", 2): (["c"], 3),
             ("14", 1): (["d"], 3), ("14", 2): ([], 1)}  # 받는 도중 전체 수가 줄어 빈 페이지
    state = fetch_all(new_state(), "KEY", out, rows=2, types=("12", "14"), fetch=_fake_pages(pages))
    assert state["types"]["12"] == {"total": 3, "next_page": 3, "done": True}
    assert state["types"]["14"]["done"] is True
    assert sorted(state["items"]) == ["a", "b", "c", "d"]
    assert sum(state["calls"].values()) == 4
    assert json.loads(out.read_text(encoding="utf-8"))["items"].keys() == state["items"].keys()


def test_quota_stops_and_resumes(tmp_path):
    out = tmp_path / "list.json"
    pages = {("12", 1): (["a", "b"], 3), ("12", 2): (["c"], 3), ("14", 1): (["d"], 1)}
    with pytest.raises(QuotaExceeded):
        fetch_all(new_state(), "KEY", out, rows=2, types=("12", "14"), fetch=_fake_pages(pages, quota_at=("12", 2)))
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["types"]["12"] == {"total": 3, "next_page": 2, "done": False}
    assert sorted(saved["items"]) == ["a", "b"]

    calls = []
    state = fetch_all(saved, "KEY", out, rows=2, types=("12", "14"), fetch=_fake_pages(pages, calls=calls))
    assert calls == [("12", 2), ("14", 1)]  # 받은 페이지는 다시 부르지 않음
    assert sorted(state["items"]) == ["a", "b", "c", "d"]
    assert all(t["done"] for t in state["types"].values())


def test_max_calls_limits_run(tmp_path):
    out = tmp_path / "list.json"
    pages = {("12", 1): (["a"], 2), ("12", 2): (["b"], 2)}
    state = fetch_all(new_state(), "KEY", out, rows=1, types=("12",), fetch=_fake_pages(pages), max_calls=1)
    assert state["types"]["12"]["next_page"] == 2 and not state["types"]["12"]["done"]


def test_saved_file_has_no_key(tmp_path):
    out = tmp_path / "list.json"
    pages = {("12", 1): (["a"], 1)}
    fetch_all(new_state(), "SECRETKEY123", out, rows=10, types=("12",), fetch=_fake_pages(pages))
    assert "SECRETKEY123" not in out.read_text(encoding="utf-8")


def test_code_names():
    from scripts.fetch_list import code_names

    rows = [{"lclsSystm1Cd": "SH", "lclsSystm1Nm": "쇼핑", "lclsSystm2Cd": "SH06", "lclsSystm2Nm": "시장",
             "lclsSystm3Cd": "SH060200", "lclsSystm3Nm": "상설시장"},
            {"lclsSystm1Cd": "SH", "lclsSystm1Nm": "쇼핑", "lclsSystm2Cd": "SH01", "lclsSystm2Nm": "백화점",
             "lclsSystm3Cd": "SH010100", "lclsSystm3Nm": "백화점"}]
    assert code_names(rows) == {"SH": "쇼핑", "SH06": "시장", "SH060200": "상설시장", "SH01": "백화점", "SH010100": "백화점"}
