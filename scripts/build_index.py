"""seoul-tour-v3 인덱스를 (다시) 만든다.

    python scripts/build_index.py

settings.opensearch_index 인덱스만 지우고 재생성한다. 다른 프로젝트 인덱스(seoul-tour·food-*)는 이름이 같으면 거부한다.
좌표가 없는 장소도 색인은 한다(location 필드만 뺌).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from opensearchpy import helpers

    from app.catalog import has_coords, load_catalog
    from app.config import ConfigError, load_settings
    from app.search import INDEX_BODY, SentenceEmbedder, build_document_text, index_name_guard, make_client

    try:
        settings = load_settings(required=("OPENSEARCH_USER", "OPENSEARCH_PASSWORD"))
    except ConfigError as e:
        print(e)
        return 1
    index = index_name_guard(settings.opensearch_index)

    catalog = load_catalog(ROOT / "data" / "seoul_tour.json", ROOT / "data" / "seoul_tour_enriched.json")
    print(f"카탈로그 {len(catalog)}건, 임베딩 모델 로딩: {settings.embed_model}")
    embedder = SentenceEmbedder(settings.embed_model)

    client = make_client(settings)
    if client.indices.exists(index=index):
        client.indices.delete(index=index)
        print(f"기존 {index} 인덱스 삭제")
    client.indices.create(index=index, body=INDEX_BODY)
    print(f"{index} 인덱스 생성")

    actions = []
    for p in catalog.values():
        content = build_document_text(p)
        doc = {
            "id": p.id, "title": p.title, "content_type": p.content_type, "kind": p.kind,
            "cat3": p.cat3, "category": p.category, "addr": p.addr, "tel": p.tel,
            "image": p.image, "content": content, "vector": embedder.encode(content),
        }
        if has_coords(p):
            doc["location"] = {"lat": p.lat, "lon": p.lng}
        actions.append({"_index": index, "_id": p.id, "_source": doc})

    ok, errors = helpers.bulk(client, actions, raise_on_error=False)
    client.indices.refresh(index=index)
    count = client.count(index=index)["count"]
    print(f"{ok}건 색인, 오류 {len(errors) if isinstance(errors, list) else errors}건, 인덱스 문서 수 {count}")
    return 0 if count == len(catalog) else 2


if __name__ == "__main__":
    sys.exit(main())
