import uuid
from datetime import datetime, timedelta

import pytest

from app.history import InMemoryHistoryRepo
from app.schemas import CenterOut, PlaceOut

PLACE = PlaceOut(id="398373", title="개성만두 궁", kind="food", category="한식", addr="서울 종로구", tel="",
                 lat=37.5743, lng=126.9854, image="", distance_m=780, walk_min=12)
CENTER = CenterOut(lat=37.5761, lng=126.9768, label="광화문", source="place")


def _mysql_repo():
    from app.config import load_settings
    from app.history import MySQLHistoryRepo

    repo = MySQLHistoryRepo(load_settings())
    repo.ensure_table()
    return repo


@pytest.fixture(params=["memory", pytest.param("mysql", marks=pytest.mark.integration)])
def repo(request):
    if request.param == "memory":
        yield InMemoryHistoryRepo()
        return
    r = _mysql_repo()
    r._test_sessions = []
    yield r
    for sid in r._test_sessions:
        r.delete_session(sid)


@pytest.fixture
def sid(repo):
    s = f"test-{uuid.uuid4()}"
    if hasattr(repo, "_test_sessions"):
        repo._test_sessions.append(s)
    return s


def test_keeps_latest_100(repo, sid):
    for i in range(101):
        repo.save(sid, "user", f"메시지 {i}")
    msgs = repo.list(sid)
    assert len(msgs) == 100
    assert msgs[0].message == "메시지 1"
    assert msgs[-1].message == "메시지 100"


def test_last_assistant_skips_casual(repo, sid):
    repo.save(sid, "user", "광화문 근처 맛집")
    repo.save(sid, "assistant", "추천해요", center=CENTER, places=[PLACE])
    repo.save(sid, "user", "고마워!")
    repo.save(sid, "assistant", "별말씀을요 😊")
    last = repo.last_assistant(sid)
    assert last is not None
    assert last.message == "추천해요"
    assert last.places[0].id == "398373"


def test_last_assistant_none(repo, sid):
    assert repo.last_assistant(sid) is None
    repo.save(sid, "assistant", "안녕하세요")
    assert repo.last_assistant(sid) is None


def test_roundtrip_center_places(repo, sid):
    repo.save(sid, "assistant", "추천해요", center=CENTER, places=[PLACE])
    msg = repo.list(sid)[0]
    assert msg.role == "assistant"
    assert msg.center == CENTER
    assert msg.places == [PLACE]
    datetime.fromisoformat(msg.created_at)
    assert "T" in msg.created_at


def test_user_message_defaults(repo, sid):
    repo.save(sid, "user", "안녕")
    msg = repo.list(sid)[0]
    assert msg.center is None
    assert msg.places == []


def test_unknown_session_empty(repo):
    assert repo.list(f"none-{uuid.uuid4()}") == []


def test_sessions_isolated(repo, sid):
    other = f"test-{uuid.uuid4()}"
    if hasattr(repo, "_test_sessions"):
        repo._test_sessions.append(other)
    repo.save(sid, "user", "a")
    repo.save(other, "user", "b")
    assert [m.message for m in repo.list(sid)] == ["a"]


def test_delete_expired_memory():
    repo = InMemoryHistoryRepo()
    repo.save("s", "user", "old")
    repo.save("s", "user", "new")
    repo._rows[0]["created_at"] = datetime.now() - timedelta(days=31)
    assert repo.delete_expired(30) == 1
    assert [m.message for m in repo.list("s")] == ["new"]


@pytest.mark.integration
def test_delete_expired_mysql():
    repo = _mysql_repo()
    sid = f"test-{uuid.uuid4()}"
    try:
        repo.save(sid, "user", "old")
        repo.save(sid, "user", "new")
        repo._execute(
            "UPDATE chat_message SET created_at = NOW() - INTERVAL 31 DAY WHERE session_id=%s AND message='old'",
            (sid,),
        )
        assert repo.delete_expired(30) >= 1
        assert [m.message for m in repo.list(sid)] == ["new"]
    finally:
        repo.delete_session(sid)
