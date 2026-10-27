import pytest

from app.search import build_document_text, build_query, index_name_guard


def _filters(q):
    return q["query"]["knn"]["vector"]["filter"]["bool"]["filter"]


def test_build_query_with_cat3():
    q = build_query([0.1] * 768, {"39"}, "A05020900", 50)
    knn = q["query"]["knn"]["vector"]
    assert knn["k"] == 50
    assert q["size"] == 50
    assert len(knn["vector"]) == 768
    assert {"terms": {"content_type": ["39"]}} in _filters(q)
    assert {"term": {"cat3": "A05020900"}} in _filters(q)


def test_build_query_without_cat3_sorted_types():
    q = build_query([0.1] * 768, {"14", "12"}, None, 100)
    assert _filters(q) == [{"terms": {"content_type": ["12", "14"]}}]


def test_index_name_guard():
    with pytest.raises(ValueError):
        index_name_guard("seoul-tour")
    with pytest.raises(ValueError):
        index_name_guard("")
    assert index_name_guard("seoul-tour-v2") == "seoul-tour-v2"


def test_document_text(small_catalog):
    text = build_document_text(small_catalog["398373"])
    assert "개성만두 궁" in text
    assert "한식" in text
    assert "종로구" in text
