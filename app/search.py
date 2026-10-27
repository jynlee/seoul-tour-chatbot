"""임베딩 + OpenSearch kNN 후보 검색.

OpenSearch는 "의미가 맞는 후보 id"만 고른다. 장소 정보·거리 계산은 카탈로그와 파이썬에서 한다.
"""
from typing import Protocol

from app.catalog import Place

PROTECTED_INDEXES = {"seoul-tour", "food-materials"}  # 다른 프로젝트 인덱스: 읽지도 쓰지도 않음
WRITE_PROTECTED_INDEXES = PROTECTED_INDEXES | {"seoul-tour-v2"}  # 574곳 확인 서버가 쓰는 인덱스: 다시 만들지 않음
VECTOR_DIM = 768
# 임베딩 모델 최대 128토큰: 기존 문장이 약 32토큰이라 개요는 앞부분 150자(약 90토큰)만 붙인다
OVERVIEW_CHARS = 150

_KIND_WORD = {"food": "음식점", "tour": "관광지", "event": "축제/행사"}


class SearchUnavailable(RuntimeError):
    """OpenSearch에 연결할 수 없음 → API는 503."""


class Embedder(Protocol):
    def encode(self, text: str) -> list[float]: ...


class Searcher(Protocol):
    def knn(self, vector: list[float], content_types: set[str], cat3: str | None, k: int) -> list[tuple[str, float]]: ...


def index_name_guard(name: str, write: bool = False) -> str:
    """write=True(인덱스 삭제·생성)면 seoul-tour-v2 도 거부."""
    protected = WRITE_PROTECTED_INDEXES if write else PROTECTED_INDEXES
    if not name or name.strip() in protected:
        raise ValueError(f"이 인덱스 이름은 쓸 수 없어요: {name!r} (보호: {', '.join(sorted(protected))})")
    return name


def build_document_text(p: Place) -> str:
    """임베딩용 문장 (기존 vectorize.py 문장 + 분류 한글명 + 개요 앞부분)."""
    kind_word = _KIND_WORD.get(p.kind, "관광지")
    where = f"서울 {p.gu}" if p.gu else "서울"
    text = (f"{p.title}는 {where}에 위치한 {kind_word}입니다. "
            f"분류는 {p.category}이며 주소는 {p.addr}입니다.")
    overview = p.overview.strip()[:OVERVIEW_CHARS]
    return f"{text} {overview}" if overview else text


def build_query(vector: list[float], content_types: set[str], cat3: str | None, k: int) -> dict:
    filters: list[dict] = [{"terms": {"content_type": sorted(content_types)}}]
    if cat3:
        filters.append({"term": {"cat3": cat3}})
    return {
        "size": k,
        "_source": ["id"],
        "query": {
            "knn": {
                "vector": {
                    "vector": vector,
                    "k": k,
                    "filter": {"bool": {"filter": filters}},
                }
            }
        },
    }


INDEX_BODY = {
    "settings": {"index": {"knn": True, "knn.algo_param.ef_search": 100}},
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "title": {"type": "text"},
            "content_type": {"type": "keyword"},
            "kind": {"type": "keyword"},
            "cat3": {"type": "keyword"},
            "category": {"type": "keyword"},
            "addr": {"type": "text"},
            "tel": {"type": "keyword"},
            "location": {"type": "geo_point"},
            "image": {"type": "keyword", "index": False},
            "content": {"type": "text"},
            "vector": {
                "type": "knn_vector",
                "dimension": VECTOR_DIM,
                "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "lucene"},
            },
        }
    },
}


def make_client(settings):
    import urllib3
    from opensearchpy import OpenSearch

    urllib3.disable_warnings()
    return OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_auth=(settings.opensearch_user, settings.opensearch_password),
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
        timeout=10,
    )


class SentenceEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def encode(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()


class OpenSearchSearcher:
    def __init__(self, settings, client=None):
        self._index = index_name_guard(settings.opensearch_index)
        self._client = client or make_client(settings)

    def knn(self, vector, content_types, cat3, k):
        try:
            result = self._client.search(index=self._index, body=build_query(vector, content_types, cat3, k))
        except Exception as e:  # 연결 실패·인덱스 없음 등 모두 검색 불가로 본다
            raise SearchUnavailable(str(e)) from e
        return [(hit["_source"]["id"], float(hit["_score"])) for hit in result["hits"]["hits"]]

    def ping(self) -> bool:
        try:
            return bool(self._client.indices.exists(index=self._index))
        except Exception:
            return False
