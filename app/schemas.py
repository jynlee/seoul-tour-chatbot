"""API 요청/응답 모델 — 팀원1·2가 합의하는 계약. 바꾸면 TEAM-STATUS.md ④에 기록."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Location(BaseModel):
    lat: float
    lng: float


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=500)
    location: Location | None = None
    selected_place_id: str | None = None

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, v):
        return v.strip() if isinstance(v, str) else v


class PlaceOut(BaseModel):
    id: str
    title: str
    kind: Literal["food", "tour"]
    category: str
    addr: str
    tel: str
    lat: float
    lng: float
    image: str
    distance_m: int | None = None
    walk_min: int | None = None


class CenterOut(BaseModel):
    lat: float
    lng: float
    label: str
    source: Literal["gps", "place", "area", "gu", "history"]


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    center: CenterOut | None = None
    places: list[PlaceOut] = []


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    message: str
    center: CenterOut | None = None
    places: list[PlaceOut] = []
    created_at: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]
