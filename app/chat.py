"""ChatService: 대화 한 턴 처리.

의도 순서:
1. 장소 정보 질문(place_info): 정보 키워드(주차·영업…)가 있거나, 순서·이름으로 장소를 가리키며 설명을 물을 때.
   단 "근처/주변/가까운/추천" 또는 "다른 데 더"가 있으면 추천이 우선. places=[], center=null (지도 유지).
2. 일상 대화(casual): 고정 답변, places=[].
3. 추천 코스: 코스 말·데이트 말이면 칸 순서대로 걸어서 이어지는 장소들. 직전 답이 코스인데 "다른 코스"면
   그 코스를 만든 질문으로 다시 짜되 같은 기준점에서 보여 준 코스 장소는 뺀다. 못 짜면 일반 추천에 안내 문장을 붙인다.
4. 추천: 빠진 카테고리는 직전 추천에서 이어받고, 가리킨 장소가 있으면 그곳이 기준점.
   "다른 데 더"는 같은 기준점에서 이미 보여 준 곳을 빼고 다음 후보.
"""
import logging
import random
import uuid
from dataclasses import dataclass
from typing import Any

from app.center import Center, has_named_area, match_place, resolve_center
from app.course import COURSE_WORDS, DATE_WORDS, build_course, plan_course
from app.dialog import (
    asked_fields, demonstrative_reference, earlier_place_lists, focus_place_id, format_history, has_demonstrative, info_value,
    intent_from_places, is_explain, is_implicit_explain, is_more_request, is_near, ordinal_out_of_range, resolve_reference, wants_whole_seoul,
)
from app.catalog import CAFE_CAT3, EVENT_TYPE, FOOD_TYPE
from app.intent import CASUAL_RESPONSES, TOUR_TOPICS, TOUR_TYPES, detect_intent
from app.llm import (
    CLARIFY_ANSWER, COURSE_FAIL_NOTICE, COURSE_HOURS_NOTE, FAR_MORE_NOTICE, GU_EMPTY_MORE_NOTICE, GU_EMPTY_NOTICE,
    GU_FILL_MORE_NOTICE, GU_FILL_NOTICE, NO_MORE_ANSWER, ORDINAL_OUT_OF_RANGE, TOPIC_MISSING_NOTICE, LLMUnavailable,
    all_far, build_course_prompt, build_info_prompt, build_prompt, course_template_answer, dropped_notice,
    info_template_answer, mentions_far, mentions_missing, mentions_other_gu, template_answer,
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

    def _reply(self, sid, user_message, answer, center=None, places=None, saved_center=None,
               course: bool = False) -> ChatResponse:
        places = places or []
        self._save(sid, "user", user_message)
        self._save(sid, "assistant", answer, center=saved_center or center, places=places)
        return ChatResponse(session_id=sid, answer=answer, center=center, places=places, course=course)

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
        ref = resolve_reference(msg, req.selected_place_id, last_places, focus_id, catalog, near=near,
                                earlier_lists=earlier_place_lists(messages))
        # "뭐하는곳인데?"처럼 지시어 없이 설명만 물으면 '거기'와 같이 본다 (새 지역·종류를 말했으면 새 추천)
        if (ref is None and not near and not more and is_implicit_explain(msg) and not intent.has_category
                and not has_named_area(msg, catalog)):
            ref = demonstrative_reference(req.selected_place_id, last_places, focus_id, catalog)
        fields = asked_fields(msg)
        history_texts = format_history(messages)

        # 1) 장소 정보 질문
        if not near and not more:
            # 되묻기 뒤 장소 이름만 답함("무료야?" → 되묻기 → "석파정") → 앞 질문(물어본 정보·설명)을 이어받는다
            prev_q = self._clarified_question(messages)
            if ref is not None and prev_q is not None and not fields and not is_explain(msg):
                return self._place_info(sid, msg, ref, asked_fields(prev_q), history_texts,
                                        question=f"{msg} {prev_q}")
            if ordinal_out_of_range(msg, last_places):
                return self._reply(sid, msg, ORDINAL_OUT_OF_RANGE.format(n=len(last_places)))
            if ref is None and has_demonstrative(msg) and is_explain(msg):
                return self._reply(sid, msg, CLARIFY_ANSWER)  # "거기 어디야?"인데 가리킬 장소가 없음
            asks_about_ref = ref is not None and (ref.kind in ("ordinal", "partial") or is_explain(msg))
            if fields or asks_about_ref:
                return self._place_info(sid, msg, ref, fields, history_texts)

        # 2) 일상 대화
        if intent.casual and ref is None:
            return self._reply(sid, msg, random.choice(CASUAL_RESPONSES))

        # 3) 추천 코스 ("다른 코스"는 코스 말이 있어도 새 코스 질문보다 먼저 판정)
        course_more = self._is_course_more(msg, more, last_places)
        course_q = self._last_course_question(messages) if course_more else msg
        plan = plan_course(course_q) if course_q else None
        if plan is not None:
            center = self._center(msg, req, ref, last, last_places, catalog)
            return self._course(sid, msg, course_q, plan, center, course_more, messages, history_texts)

        # 4) 추천
        if not intent.has_category and last_places:
            intent = intent_from_places(last_places, catalog) or intent
            # "다른 데 더"·"거기 근처는?"도 직전 관광 세부 주제(산책 등)를 이어받음
            if intent.content_types and intent.content_types <= TOUR_TYPES | {EVENT_TYPE}:
                intent.topic = self._last_topic(messages)
        center = self._center(msg, req, ref, last, last_places, catalog)
        label = center.label if center else None
        exclude = self._shown_ids(messages, label) if more else set()
        return self._recommend(sid, msg, intent, center, more, exclude, history_texts)

    @staticmethod
    def _center(msg, req, ref, last, last_places, catalog) -> Center | None:
        """기준점: 가리킨 장소가 있으면 그곳, 아니면 resolve_center (코스·일반 추천이 같이 씀)."""
        if req.location is None and ref is not None and not has_named_area(msg, catalog):
            p = ref.place
            return Center(lat=p.lat, lng=p.lng, label=p.title, source="place", place_id=p.id)
        # '서울에서…'·주제만 묻는 새 질문은 직전 기준점을 이어받지 않음 (지역·장소 이름이 있으면 그것대로)
        last_center = last.center if last and not wants_whole_seoul(msg) else None
        return resolve_center(msg, req.location, req.selected_place_id, last_places, last_center, catalog)

    def _recommend(self, sid, msg, intent, center, more, exclude, history_texts, prefix=None) -> ChatResponse:
        """일반 추천 답. prefix가 있으면 답 맨 앞에 붙인다 (코스 실패 안내)."""
        catalog = self.deps.catalog
        label = center.label if center else None
        # SearchUnavailable 은 그대로 올린다 (API에서 503)
        rec = recommend(msg, intent, center, self.deps.searcher, self.deps.embedder, catalog, exclude_ids=exclude)
        center_out = center.to_out() if center else None
        if more and not rec.places:
            return self._reply(sid, msg, NO_MORE_ANSWER.format(label=f"{label} 근처" if label else "이"))

        # "다른 데 더"인데 남은 곳이 모두 반경 밖이면 멀다는 사실을 꼭 알린다 (LLM이 빠뜨리면 안내 문장을 앞에 붙임)
        far = more and label and not rec.gu_wide and all_far(rec.places)
        far_notice = FAR_MORE_NOTICE.format(label=label) if far else None
        # 산책 등 세부 주제에 맞는 곳이 하나도 없으면 솔직히 말한다 (같은 방식)
        topic_label = TOUR_TOPICS[intent.topic].label if intent.topic else None
        missing_notice = (TOPIC_MISSING_NOTICE.format(where=f"{label}에서 " if label else "", topic=topic_label)
                          if rec.topic_missing else None)
        # 구 기준점인데 구 안에 맞는 곳이 없거나 적어 다른 구 장소를 골랐으면 그 사실을 꼭 알린다 (QA-9, 같은 방식)
        gu_notice, other_gus = self._gu_notice(rec, label, intent, more)
        try:
            answer = self.deps.llm.generate(
                build_prompt(msg, history_texts, rec.places, label, rec.fallback_note, more=more,
                             far_notice=far_notice, topic_label=topic_label, topic_missing=rec.topic_missing,
                             gu_wide=rec.gu_wide, place_gus=rec.place_gus, gu_empty=rec.gu_empty,
                             what=self._what(intent)[0]))
            if far_notice and not mentions_far(answer):
                answer = f"{far_notice} {answer}"
            if missing_notice and not mentions_missing(answer):
                answer = f"{missing_notice} {answer}"
            told = mentions_other_gu(answer, other_gus) and (not rec.gu_empty or mentions_missing(answer))
            if gu_notice and not told:
                answer = f"{gu_notice} {answer}"
        except LLMUnavailable:
            answer = template_answer(rec.places, label, far=far_notice is not None or rec.gu_empty)
            if rec.fallback_note and rec.places:
                answer = f"{answer} ({rec.fallback_note})"
            if far_notice:
                answer = f"{far_notice} {answer}"
            if missing_notice:
                answer = f"{missing_notice} {answer}"
            if gu_notice:
                answer = f"{gu_notice} {answer}"
        if prefix:
            answer = f"{prefix} {answer}"
        return self._reply(sid, msg, answer, center=center_out, places=rec.places)

    def _course(self, sid, msg, course_q, plan, center, more, messages, history_texts) -> ChatResponse:
        """코스 답. 못 짜면(3곳 미만) 그 질문으로 일반 관광 추천을 하고 코스를 못 짰다는 사실을 앞에 밝힌다."""
        label = center.label if center else None
        exclude = self._shown_course_ids(messages, label) if more else set()
        # SearchUnavailable 은 그대로 올린다 (API에서 503)
        result = build_course(course_q, plan, center, self.deps.searcher, self.deps.embedder, self.deps.catalog,
                              exclude_ids=exclude)
        if not result.ok:
            if more and not result.places:
                return self._reply(sid, msg, NO_MORE_ANSWER.format(label=f"{label} 근처" if label else "이"))
            intent = detect_intent(course_q)
            if not intent.has_category:
                intent.content_types = set(TOUR_TYPES)
            if center is None:
                where = ""
            elif center.source in ("place", "gps"):
                where = f"{label} 근처에서는 "
            else:
                where = f"{label}에서는 "  # 구·지역 이름: "성동구에서는", "홍대에서는"
            return self._recommend(sid, msg, intent, center, more, exclude, history_texts,
                                   prefix=COURSE_FAIL_NOTICE.format(where=where))

        notice = dropped_notice(result.dropped)
        try:
            answer = self.deps.llm.generate(
                build_course_prompt(msg, history_texts, result.places, label, result.dropped))
        except LLMUnavailable:
            answer = course_template_answer(result.places)
        # 뺀 칸 안내·영업시간 안내는 LLM이 빠뜨려도 꼭 들어가게
        if notice and notice not in answer:
            answer = f"{notice} {answer}"
        if COURSE_HOURS_NOTE not in answer:
            answer = f"{answer} {COURSE_HOURS_NOTE}"
        center_out = center.to_out() if center else None
        return self._reply(sid, msg, answer, center=center_out, places=result.places, course=True)

    def _is_course_more(self, msg, more, last_places) -> bool:
        """직전 답이 코스인데 "다른 데 더"·"다른 코스"·"또 코스"처럼 물었는지.
        스스로 칸 계획(데이트·맛집·카페…)이 있거나 장소·지역 이름이 있으면 새 코스 질문이다 (Ruling 7)."""
        if not last_places or last_places[0].step is None:
            return False
        if not (more or (("다른" in msg or "또" in msg) and any(w in msg for w in COURSE_WORDS))):
            return False
        own = plan_course(msg)
        if own is not None and own.theme != "default":
            return False
        # 코스 말 없이 장소 종류(맛집·카페·관광 세부 주제…)를 콕 집었으면 그 종류의 "다른 데 더" (Ruling 12)
        if not any(w in msg for w in COURSE_WORDS):
            text = msg
            for w in DATE_WORDS:
                text = text.replace(w, " ")
            if detect_intent(text).has_category:
                return False
        return not has_named_area(msg, self.deps.catalog) and match_place(msg, self.deps.catalog) is None

    def _last_course_question(self, messages) -> str | None:
        """마지막 코스를 만든 처음 질문: 코스 답을 받았고 그 자신은 "다른 코스"가 아니었던 마지막 사용자 질문."""
        origin = None
        prev_places = []  # 그 질문 때의 직전 추천 (handle 의 last_places 와 같음)
        for i, m in enumerate(messages):
            if m.role == "user" and i + 1 < len(messages):
                bot = messages[i + 1]
                got_course = bot.role == "assistant" and bot.places and bot.places[0].step is not None
                if got_course and not self._is_course_more(m.message, is_more_request(m.message), prev_places):
                    origin = m.message
            if m.role == "assistant" and m.places:
                prev_places = m.places
        return origin

    @staticmethod
    def _shown_course_ids(messages, label) -> set[str]:
        """같은 기준점에서 이미 보여 준 코스 장소 ("다른 코스"에서 뺄 곳)."""
        shown = set()
        for m in messages:
            if (m.role == "assistant" and m.places and m.places[0].step is not None
                    and (m.center.label if m.center else None) == label):
                shown.update(p.id for p in m.places)
        return shown

    @staticmethod
    def _what(intent) -> tuple[str, str]:
        """안내 문장에 쓸 찾는 대상 이름 (그대로, 목적격)."""
        types = intent.content_types or set()
        if intent.cat3 == CAFE_CAT3:
            return "카페", "카페를"
        if types == {FOOD_TYPE}:
            return "음식점", "음식점을"
        if types == {EVENT_TYPE}:
            return "축제·행사", "축제·행사를"
        if types and types <= TOUR_TYPES | {EVENT_TYPE}:
            return "관광지", "관광지를"
        return "장소", "장소를"

    @classmethod
    def _gu_notice(cls, rec, gu, intent, more) -> tuple[str | None, list[str]]:
        """구 결과에 다른 구 장소가 섞였을 때 앞에 붙일 안내 문장과 그 다른 구 이름들."""
        if not rec.gu_wide or not rec.places:
            return None, []
        others = list(dict.fromkeys(rec.place_gus[p.id] for p in rec.places
                                    if p.id in rec.place_gus and rec.place_gus[p.id] != gu))
        if not others:
            return None, []
        if rec.gu_empty:
            what, what_obj = cls._what(intent)
            return (GU_EMPTY_MORE_NOTICE if more else GU_EMPTY_NOTICE).format(gu=gu, what=what, what_obj=what_obj), others
        n = sum(1 for p in rec.places if rec.place_gus.get(p.id) == gu)
        return (GU_FILL_MORE_NOTICE if more else GU_FILL_NOTICE).format(gu=gu, n=n, others="·".join(others)), others

    @staticmethod
    def _clarified_question(messages) -> str | None:
        """직전 챗봇 답이 장소를 되물은 것(CLARIFY_ANSWER)이면 그 앞 사용자 질문."""
        if len(messages) < 2:
            return None
        bot, user = messages[-1], messages[-2]
        if bot.role == "assistant" and bot.message == CLARIFY_ANSWER and user.role == "user":
            return user.message
        return None

    @staticmethod
    def _last_topic(messages) -> str | None:
        """마지막 추천을 만든 사용자 질문의 관광 세부 주제."""
        for i in range(len(messages) - 1, 0, -1):
            m = messages[i]
            if m.role == "assistant" and m.places:
                prev = messages[i - 1]
                return detect_intent(prev.message).topic if prev.role == "user" else None
        return None

    @staticmethod
    def _shown_ids(messages, label) -> set[str]:
        """같은 기준점에서 이미 보여 준 장소 ("다른 데 더 추천해줘"에서 뺄 곳)."""
        shown = set()
        for m in messages:
            if m.role == "assistant" and m.places and (m.center.label if m.center else None) == label:
                shown.update(p.id for p in m.places)
        return shown

    def _place_info(self, sid, msg, ref, fields, history_texts, question=None) -> ChatResponse:
        if ref is None:
            return self._reply(sid, msg, CLARIFY_ANSWER)
        place = ref.place
        if fields and not any(info_value(place, f) for f in fields):
            answer = info_template_answer(place, fields)  # 물어본 정보가 하나도 없음 → 지어내지 않게 LLM 생략
        else:
            try:
                answer = self.deps.llm.generate(build_info_prompt(question or msg, history_texts, place, fields))
            except LLMUnavailable:
                answer = info_template_answer(place, fields)
        # 응답은 center=null·places=[] (지도 유지). 기록에는 설명한 장소를 center 로 남겨 다음 "거기"가 이 장소를 가리키게 함.
        focus = CenterOut(lat=place.lat, lng=place.lng, label=place.title, source="place")
        return self._reply(sid, msg, answer, center=None, places=[], saved_center=focus)
