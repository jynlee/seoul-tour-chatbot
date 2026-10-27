"""FastAPI 앱: /api/* + 정적 화면(static/).

실행: uvicorn app.main:create_app --factory --port 8000
모듈 import 시 create_app()을 호출하지 않는다 (테스트가 실제 서비스에 붙지 않도록).
"""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.chat import ChatService, Deps
from app.schemas import ChatRequest, ChatResponse, HistoryResponse
from app.search import SearchUnavailable

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
SEARCH_UNAVAILABLE_DETAIL = "검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."


def build_real_deps() -> Deps:
    from app.catalog import load_catalog
    from app.config import load_settings
    from app.history import MySQLHistoryRepo
    from app.llm import OllamaLLM
    from app.search import OpenSearchSearcher, SentenceEmbedder

    settings = load_settings()
    history = MySQLHistoryRepo(settings)
    try:
        history.ensure_table()
    except Exception:
        log.exception("chat_message 테이블 확인 실패 (MySQL 연결 확인 필요)")
    return Deps(
        catalog=load_catalog(ROOT / "data" / "seoul_tour.json", ROOT / "data" / "seoul_tour_enriched.json"),
        embedder=SentenceEmbedder(settings.embed_model),
        searcher=OpenSearchSearcher(settings),
        llm=OllamaLLM(settings),
        history=history,
    )


def _ping(dep) -> bool:
    try:
        return bool(dep.ping())
    except Exception:
        return False


def create_app(deps: Deps | None = None) -> FastAPI:
    if deps is None:
        deps = build_real_deps()
    service = ChatService(deps)

    try:
        removed = deps.history.delete_expired(30)
        if removed:
            log.info("30일 지난 대화 기록 %d건 삭제", removed)
    except Exception:
        log.exception("오래된 대화 기록 삭제 실패")

    app = FastAPI(title="서울 여행 친구")
    app.state.deps = deps

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        try:
            return service.handle(req)
        except SearchUnavailable:
            log.exception("검색 서버 연결 실패")
            raise HTTPException(status_code=503, detail=SEARCH_UNAVAILABLE_DETAIL)

    @app.get("/api/history/{session_id}", response_model=HistoryResponse)
    def history(session_id: str) -> HistoryResponse:
        return HistoryResponse(session_id=session_id, messages=deps.history.list(session_id))

    @app.get("/api/health")
    def health() -> dict:
        return {
            "opensearch": _ping(deps.searcher),
            "ollama": _ping(deps.llm),
            "mysql": _ping(deps.history),
        }

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
