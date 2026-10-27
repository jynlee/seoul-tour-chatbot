import json

import pytest

from scripts.enrich_tel import QuotaExceeded
from scripts.fetch_overview import clean_overview, fetch_overviews, new_state, order_items


def _items(*pairs):
    return [{"contentid": cid, "contenttypeid": t, "title": f"t{cid}"} for cid, t in pairs]


def test_clean_overview():
    assert clean_overview("조선 왕조의 법궁.<br>1395년 창건<br />  &nbsp;") == "조선 왕조의 법궁. 1395년 창건"
    assert clean_overview("<b>공원</b> &amp; 숲") == "공원 & 숲"
    assert clean_overview(None) == ""


def test_order_items_by_spec_priority():
    items = _items(("a", "38"), ("b", "39"), ("c", "15"), ("d", "12"), ("e", "28"), ("f", "14"))
    assert [i["contentid"] for i in order_items(items)] == ["d", "f", "b", "e", "c", "a"]


def _fake_call(texts: dict, quota_after=None, calls=None, fail=()):
    def call(operation, api_key, **params):
        assert operation == "detailCommon2"
        cid = params["contentId"]
        if calls is not None:
            calls.append(cid)
        if quota_after is not None and len(calls) > quota_after:
            raise QuotaExceeded("LIMITED_NUMBER_OF_SERVICE_REQUESTS")
        if cid in fail:
            raise RuntimeError("timeout")
        return {"contentid": cid, "overview": texts.get(cid, "")}
    return call


def test_fetch_saves_each_and_skips_done(tmp_path):
    out = tmp_path / "ov.json"
    items = _items(("a", "12"), ("b", "39"))
    state = new_state()
    state["overview"]["a"] = "이미 받음"
    calls = []
    done, failed = fetch_overviews(items, state, "KEY", out, call=_fake_call({"b": "맛집<br>설명"}, calls=calls))
    assert calls == ["b"] and (done, failed) == (1, 0)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["overview"] == {"a": "이미 받음", "b": "맛집 설명"}
    assert sum(saved["calls"].values()) == 1


def test_empty_overview_is_saved_so_not_refetched(tmp_path):
    out = tmp_path / "ov.json"
    state = new_state()
    fetch_overviews(_items(("a", "12")), state, "KEY", out, call=_fake_call({}, calls=[]))
    assert state["overview"] == {"a": ""}


def test_quota_stops_with_progress_saved(tmp_path):
    out = tmp_path / "ov.json"
    items = _items(("a", "12"), ("b", "12"), ("c", "12"))
    calls = []
    with pytest.raises(QuotaExceeded):
        fetch_overviews(items, new_state(), "KEY", out, call=_fake_call({"a": "A"}, quota_after=1, calls=calls))
    assert json.loads(out.read_text(encoding="utf-8"))["overview"] == {"a": "A"}


def test_failure_not_saved_and_limit(tmp_path):
    out = tmp_path / "ov.json"
    items = _items(("a", "12"), ("b", "12"), ("c", "12"))
    state = new_state()
    done, failed = fetch_overviews(items, state, "KEY", out, call=_fake_call({}, calls=[], fail=("a",)), limit=1)
    assert (done, failed) == (1, 1)
    assert list(state["overview"]) == ["b"]
    assert sum(state["calls"].values()) == 2  # 실패한 호출도 한도에 들어가므로 센다
