from app.geo import AREAS, SEOUL_GU, haversine_m, walk_min


def test_haversine_gwanghwamun_to_gaesung():
    d = haversine_m(37.5761, 126.9768, 37.5743, 126.9854)
    assert 740 <= d <= 820


def test_walk_min():
    assert walk_min(780) == 12
    assert walk_min(10) == 1
    assert walk_min(0) == 1


def test_constants():
    assert len(SEOUL_GU) == 25
    assert AREAS["성수"] == (37.5446, 127.0559)
    assert len(AREAS) == 32
