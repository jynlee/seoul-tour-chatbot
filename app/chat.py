"""ChatService: 대화 한 턴 처리.

의도 순서:
1. 장소 정보 질문(place_info): 정보 키워드(주차·영업…)가 있거나, 순서·이름으로 장소를 가리키며 설명을 물을 때.
   단 "근처/주변/가까운/추천" 또는 "다른 데 더"가 있으면 추천이 우선. places=[], center=null (지도 유지).
2. 일상 대화(casual): 고정 답변, places=[].
3. 추천: 빠진 카테고리는 직전 추천에서 이어받고, 가리킨 장소가 있으면 그곳이 기준점.
   "다른 데 더"는 같은 기준점에서 이미 보여 준 곳을 빼고 다음 후보.
"""
import logging
import random
import uuid
from dataclasses import dataclass
from typing import Any

from app.center import Center, has_named_area, resolve_center
from app.dialog import (
    asked_fields, focus_place_id, format_history, info_value, intent_from_places, is_explain, is_more_request,
    is_near, resolve_reference,
)
from app.intent import CASUAL_RESPONSES, detect_intent
from app.llm import (
    CLARIFY_ANSWER, FAR_MORE_NOTICE, NO_MORE_ANSWER, LLMUnavailable, all_far, build_info_prompt, build_prompt,
    info_template_answer, mentions_far, template_answer,
)
from app.recommend import recommend
from app.schemas import CenterOut, ChatRequest, ChatResponse

log = logging.getLogger(__name__)


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

    def _reply(self, sid, user_message, answer, center=None, places=None, saved_center=None) -> ChatResponse:
        places = places or []
        self._save(sid, "user", user_message)
        self._save(sid, "assistant", answer, center=saved_center or center, places=places)
        return ChatResponse(session_id=sid, answer=answer, center=center, places=places)

    def handle(self, req: ChatRequest) -> ChatResponse:
        sid = req.session_id or str(uuid.uuid4())
        msg = req.message
        catalog = self.deps.catalog
        intent = detect_intent(msg)

        messages, last = self._history(sid)
        last_places = last.places if last else []
        focus_id = focus_place_id(messages, last_places, catalog)
        near = is_near(msg)
        more = is_more_request(msg)
        ref = resolve_reference(msg, req.selected_place_id, last_places, focus_id, catalog, near=near)
        fields = asked_fields(msg)
        history_texts = format_history(messages)

        # 1) 장소 정보 질문
        if not near and not more:
            asks_about_ref = ref is not None and (ref.kind in ("ordinal", "partial") or is_explain(msg))
            if fields or asks_about_ref:
                return self._place_info(sid, msg, ref, fields, history_texts)

        # 2) 일상 대화
        if intent.casual and ref is None:
            return self._reply(sid, msg, random.choice(CASUAL_RESPONSES))

        # 3) 추천
        if not intent.has_category and last_places:
            intent = intent_from_places(last_places, catalog) or intent
        if req.location is None and ref is not None and not has_named_area(msg, catalog):
            p = ref.place
            center = Center(lat=p.lat, lng=p.lng, label=p.title, source="place", place_id=p.id)
        else:
            center = resolve_center(msg, req.location, req.selected_place_id, last_places,
                                    last.center if last else None, catalog)
        label = center.label if center else None
        exclude = self._shown_ids(messages, label) if more else set()

        # SearchUnavailable 은 그대로 올린다 (API에서 503)
        rec = recommend(msg, intent, center, self.deps.searcher, self.deps.embedder, catalog, exclude_ids=exclude)
        center_out = center.to_out() if center else None
        if more and not rec.places:
            return self._reply(sid, msg, NO_MORE_ANSWER.format(label=f"{label} 근처" if label else "이"))

        # "다른 데 더"인데 남은 곳이 모두 반경 밖이면 멀다는 사실을 꼭 알린다 (LLM이 빠뜨리면 안내 문장을 앞에 붙임)
        far_notice = FAR_MORE_NOTICE.format(label=label) if more and label and all_far(rec.places) else None
        try:
            answer = self.deps.llm.generate(
                build_prompt(msg, history_texts, rec.places, label, rec.fallback_note, more=more,
                             far_notice=far_notice))
            if far_notice and not mentions_far(answer):
                answer = f"{far_notice} {answer}"
        except LLMUnavailable:
            answer = template_answer(rec.places, label, far=far_notice is not None)
            if rec.fallback_note and rec.places:
                answer = f"{answer} ({rec.fallback_note})"
            if far_notice:
                answer = f"{far_notice} {answer}"
        return self._reply(sid, msg, answer, center=center_out, places=rec.places)

    @staticmethod
    def _shown_ids(messages, label) -> set[str]:
        """같은 기준점에서 이미 보여 준 장소 ("다른 데 더 추천해줘"에서 뺄 곳)."""
        shown = set()
        for m in messages:
            if m.role == "assistant" and m.places and (m.center.label if m.center else None) == label:
                shown.update(p.id for p in m.places)
        return shown

    def _place_info(self, sid, msg, ref, fields, history_texts) -> ChatResponse:
        if ref is None:
            return self._reply(sid, msg, CLARIFY_ANSWER)
        place = ref.place
        if fields and not any(info_value(place, f) for f in fields):
            answer = info_template_answer(place, fields)  # 물어본 정보가 하나도 없음 → 지어내지 않게 LLM 생략
        else:
            try:
                answer = self.deps.llm.generate(build_info_prompt(msg, history_texts, place, fields))
            except LLMUnavailable:
                answer = info_template_answer(place, fields)
        # 응답은 center=null·places=[] (지도 유지). 기록에는 설명한 장소를 center 로 남겨 다음 "거기"가 이 장소를 가리키게 함.
        focus = CenterOut(lat=place.lat, lng=place.lng, label=place.title, source="place")
        return self._reply(sid, msg, answer, center=None, places=[], saved_center=focus)
