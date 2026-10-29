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
        index_name_guard("")
    assert index_name_guard("seoul-tour") == "seoul-tour"


def test_document_text(small_catalog):
    text = build_document_text(small_catalog["398373"])
    assert "개성만두 궁" in text
    assert "한식" in text
    assert "종로구" in text


def test_guard_protects_other_project_indexes():
    for name in ("food-materials", "food-law-articles", "food-qa-cache", " food-materials "):
        with pytest.raises(ValueError):
            index_name_guard(name)


def test_document_text_includes_overview_cut(small_catalog):
    from dataclasses import replace

    from app.search import OVERVIEW_CHARS

    p = replace(small_catalog["126512"], overview="조선의 정문. " + "가" * 500)
    text = build_document_text(p)
    assert text.startswith(build_document_text(small_catalog["126512"]))
    assert "조선의 정문." in text
    assert len(text) - len(build_document_text(small_catalog["126512"])) <= OVERVIEW_CHARS + 1
    assert build_document_text(small_catalog["126512"]).endswith("입니다.")  # 개요 없으면 기존 문장 그대로


def test_catalog_loads_overview(tmp_path):
    import json

    from app.catalog import load_catalog

    enriched = tmp_path / "e.json"
    enriched.write_text(json.dumps({"126512": {"overview": "광화문 설명"}}), encoding="utf-8")
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps({"response": {"body": {"items": {"item": [
        {"contentid": "126512", "contenttypeid": "12", "title": "광화문", "cat2": "A0201", "cat3": "A02010300"}]}}}}),
        encoding="utf-8")
    assert load_catalog(raw, enriched)["126512"].overview == "광화문 설명"


def test_build_query_with_near_adds_geo_distance_filter():
    # 품질 ①: 반경 기준 추천은 반경 안에서 kNN (lucene 엔진 efficient filtering)
    q = build_query([0.1] * 768, {"39"}, None, 100, near=(37.5690, 126.9780, 1500))
    assert {"geo_distance": {"distance": "1500m", "location": {"lat": 37.5690, "lon": 126.9780}}} in _filters(q)
    assert {"terms": {"content_type": ["39"]}} in _filters(q)
