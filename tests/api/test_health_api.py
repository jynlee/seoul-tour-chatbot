"""Q1: GET /api/health — 의존성별 bool."""
import pytest


def test_health_all_up(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"opensearch": True, "ollama": True, "mysql": True}


@pytest.mark.parametrize("dep,key", [("searcher", "opensearch"), ("llm", "ollama")])
def test_health_one_down(client, deps, dep, key):
    getattr(deps, dep).fail = True
    body = client.get("/api/health").json()
    assert body[key] is False
    assert all(v is True for k, v in body.items() if k != key)


def test_health_ping_raises_is_false(client, deps):
    def boom():
        raise ConnectionError("꺼짐")

    deps.history.ping = boom
    deps.searcher.ping = boom
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"opensearch": False, "ollama": True, "mysql": False}


def test_health_values_are_bool(client, deps):
    deps.llm.ping = lambda: "yes"  # truthy 값도 bool로
    body = client.get("/api/health").json()
    assert all(isinstance(v, bool) for v in body.values())
