"""ChatService: 대화 한 턴 처리."""
import logging
import random
import uuid
from dataclasses import dataclass
from typing import Any

from app.center import resolve_center
from app.intent import CASUAL_RESPONSES, detect_intent
from app.llm import LLMUnavailable, build_prompt, template_answer
from app.recommend import recommend
from app.schemas import ChatRequest, ChatResponse

log = logging.getLogger(__name__)

_ROLE_LABEL = {"user": "사용자", "assistant": "챗봇"}


@dataclass
class Deps:
    catalog: dict
    embedder: Any
    searcher: Any
    llm: Any
    history: Any


class ChatService:
    def __init__(self, deps: Deps):
        self.deps = deps

    def _save(self, sid, role, message, center=None, places=None):
        try:
            self.deps.history.save(sid, role, message, center=center, places=places)
        except Exception:  # 기록 저장 실패가 채팅 자체를 막지 않도록
            log.exception("대화 기록 저장 실패 (session=%s)", sid)

    def _history(self, sid):
        try:
            return self.deps.history.list(sid), self.deps.history.last_assistant(sid)
        except Exception:
            log.exception("대화 기록 조회 실패 (session=%s)", sid)
            return [], None

    def handle(self, req: ChatRequest) -> ChatResponse:
        sid = req.session_id or str(uuid.uuid4())
        intent = detect_intent(req.message)

        if intent.casual:
            answer = random.choice(CASUAL_RESPONSES)
            self._save(sid, "user", req.message)
            self._save(sid, "assistant", answer)
            return ChatResponse(session_id=sid, answer=answer, center=None, places=[])

        messages, last = self._history(sid)
        center = resolve_center(
            req.message, req.location, req.selected_place_id,
            last.places if last else [], last.center if last else None, self.deps.catalog,
        )
        # SearchUnavailable 은 그대로 올린다 (API에서 503)
        rec = recommend(req.message, intent, center, self.deps.searcher, self.deps.embedder, self.deps.catalog)
        label = center.label if center else None

        history_texts = [f"{_ROLE_LABEL.get(m.role, m.role)}: {m.message}" for m in messages]
        try:
            answer = self.deps.llm.generate(build_prompt(req.message, history_texts, rec.places, label, rec.fallback_note))
        except LLMUnavailable:
            answer = template_answer(rec.places, label)
            if rec.fallback_note and rec.places:
                answer = f"{answer} ({rec.fallback_note})"

        center_out = center.to_out() if center else None
        self._save(sid, "user", req.message)
        self._save(sid, "assistant", answer, center=center_out, places=rec.places)
        return ChatResponse(session_id=sid, answer=answer, center=center_out, places=rec.places)
