"""Q1: GET /api/history/{session_id} — 순서·형식·왕복."""
import re

from tests.api.conftest import chat

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def test_history_order_and_format(client):
    _, a1 = chat(client, "광화문 근처 맛집 추천해줘")
    sid = a1["session_id"]
    _, a2 = chat(client, "고마워!", session_id=sid)
    _, a3 = chat(client, "거기 근처 카페 있어?", session_id=sid, selected_place_id="398373")

    r = client.get(f"/api/history/{sid}")
    assert r.status_code == 200
    h = r.json()
    assert set(h) == {"session_id", "messages"}
    assert h["session_id"] == sid
    msgs = h["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"] * 3
    assert [m["message"] for m in msgs] == [
        "광화문 근처 맛집 추천해줘", a1["answer"], "고마워!", a2["answer"], "거기 근처 카페 있어?", a3["answer"],
    ]
    for m in msgs:
        assert set(m) == {"role", "message", "center", "places", "created_at"}
        assert ISO.match(m["created_at"]), m["created_at"]
    times = [m["created_at"] for m in msgs]
    assert times == sorted(times)  # 오래된 순
    # user 메시지는 center:null, places:[]
    for m in msgs[0::2]:
        assert m["center"] is None and m["places"] == []


def test_history_center_and_places_roundtrip(client):
    _, a1 = chat(client, "광화문 근처 맛집 추천해줘")
    sid = a1["session_id"]
    _, a2 = chat(client, "고마워!", session_id=sid)
    msgs = client.get(f"/api/history/{sid}").json()["messages"]
    assert msgs[1]["center"] == a1["center"]
    assert msgs[1]["places"] == a1["places"]
    # 일상 대화 답변은 center:null, places:[]
    assert msgs[3]["center"] is None and msgs[3]["places"] == []


def test_history_unknown_session(client):
    r = client.get("/api/history/없는세션")
    assert r.status_code == 200
    assert r.json() == {"session_id": "없는세션", "messages": []}


def test_history_sessions_isolated(client):
    _, a = chat(client, "광화문 근처 맛집 추천해줘")
    _, b = chat(client, "종로 관광지")
    ha = client.get(f"/api/history/{a['session_id']}").json()["messages"]
    hb = client.get(f"/api/history/{b['session_id']}").json()["messages"]
    assert [m["message"] for m in ha][0] == "광화문 근처 맛집 추천해줘"
    assert [m["message"] for m in hb][0] == "종로 관광지"
    assert len(ha) == len(hb) == 2


def test_history_not_saved_on_503(client, deps):
    _, a = chat(client, "광화문 근처 맛집 추천해줘")
    deps.searcher.fail = True
    r = client.post("/api/chat", json={"session_id": a["session_id"], "message": "관광지도 알려줘"})
    assert r.status_code == 503
    msgs = client.get(f"/api/history/{a['session_id']}").json()["messages"]
    # 실패한 턴은 기록에 반쪽(사용자 메시지만)으로 남지 않는다
    assert len(msgs) % 2 == 0
