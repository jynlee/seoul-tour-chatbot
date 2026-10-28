from app.history import InMemoryHistoryRepo
from app.schemas import ChatResponse, PlaceOut


def _place(**extra):
    base = dict(id="1", title="t", kind="tour", category="c", addr="a", tel="",
                lat=37.5, lng=127.0, image="")
    base.update(extra)
    return PlaceOut(**base)


def test_place_out_course_fields_default_none():
    p = _place()
    assert (p.step, p.leg_m, p.leg_walk_min) == (None, None, None)


def test_chat_response_course_default_false():
    assert ChatResponse(session_id="s", answer="a").course is False


def test_history_roundtrip_keeps_step():
    repo = InMemoryHistoryRepo()
    p = _place(id="398373", title="카페", kind="food", category="카페/전통찻집",
               step="카페", leg_m=420, leg_walk_min=6)
    repo.save("test-s", "assistant", "a", places=[p])
    got = repo.last_assistant("test-s").places[0]
    assert (got.step, got.leg_m, got.leg_walk_min) == ("카페", 420, 6)
