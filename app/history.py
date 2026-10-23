"""대화 기록 저장소 (chat_message 테이블 / 메모리).

봇 답변마다 기준점(center)과 추천 장소(places)를 함께 저장해 새로고침 시 지도까지 복원한다.
세션의 "직전 기준점·직전 추천 장소"는 마지막으로 장소가 있었던 봇 메시지에서 읽는다.
"""
import json
import threading
from datetime import datetime, timedelta
from typing import Protocol

from app.schemas import CenterOut, HistoryMessage, PlaceOut

MAX_PER_SESSION = 100

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_message (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL,
    message TEXT NOT NULL,
    center_json JSON NULL,
    places_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_chat_message_session (session_id, id),
    INDEX idx_chat_message_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


class HistoryRepo(Protocol):
    def save(self, session_id: str, role: str, message: str,
             center: CenterOut | None = None, places: list[PlaceOut] | None = None) -> None: ...

    def list(self, session_id: str) -> list[HistoryMessage]: ...

    def last_assistant(self, session_id: str) -> HistoryMessage | None: ...

    def delete_expired(self, days: int = 30) -> int: ...

    def ping(self) -> bool: ...


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _to_message(role, message, center, places, created_at: datetime) -> HistoryMessage:
    return HistoryMessage(role=role, message=message, center=center, places=list(places or []),
                          created_at=_iso(created_at))


class InMemoryHistoryRepo:
    """테스트·개발용. MySQL 구현과 같은 동작."""

    def __init__(self):
        self._rows: list[dict] = []
        self._lock = threading.Lock()

    def save(self, session_id, role, message, center=None, places=None):
        with self._lock:
            self._rows.append({
                "session_id": session_id, "role": role, "message": message,
                "center": center, "places": list(places or []), "created_at": datetime.now(),
            })
            mine = [r for r in self._rows if r["session_id"] == session_id]
            extra = len(mine) - MAX_PER_SESSION
            if extra > 0:
                drop = {id(r) for r in mine[:extra]}
                self._rows = [r for r in self._rows if id(r) not in drop]

    def _session_rows(self, session_id):
        return [r for r in self._rows if r["session_id"] == session_id]

    def list(self, session_id):
        with self._lock:
            return [_to_message(r["role"], r["message"], r["center"], r["places"], r["created_at"])
                    for r in self._session_rows(session_id)]

    def last_assistant(self, session_id):
        with self._lock:
            for r in reversed(self._session_rows(session_id)):
                if r["role"] == "assistant" and r["places"]:
                    return _to_message(r["role"], r["message"], r["center"], r["places"], r["created_at"])
        return None

    def delete_expired(self, days=30):
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            before = len(self._rows)
            self._rows = [r for r in self._rows if r["created_at"] >= cutoff]
            return before - len(self._rows)

    def ping(self):
        return True


class MySQLHistoryRepo:
    def __init__(self, settings):
        self._settings = settings

    def _connect(self):
        import pymysql

        s = self._settings
        return pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                               password=s.mysql_password, database=s.mysql_db, charset="utf8mb4",
                               autocommit=True, connect_timeout=5)

    def _execute(self, sql, params=()):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount
        finally:
            conn.close()

    def _query(self, sql, params=()):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def ensure_table(self):
        self._execute(CREATE_TABLE_SQL)

    def save(self, session_id, role, message, center=None, places=None):
        center_json = json.dumps(center.model_dump(), ensure_ascii=False) if center else None
        places_json = json.dumps([p.model_dump() for p in places], ensure_ascii=False) if places else None
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chat_message (session_id, role, message, center_json, places_json) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (session_id, role, message, center_json, places_json),
                )
                cur.execute(
                    "DELETE FROM chat_message WHERE session_id=%s AND id NOT IN ("
                    " SELECT id FROM (SELECT id FROM chat_message WHERE session_id=%s"
                    " ORDER BY id DESC LIMIT %s) AS keep_rows)",
                    (session_id, session_id, MAX_PER_SESSION),
                )
        finally:
            conn.close()

    @staticmethod
    def _row_to_message(row) -> HistoryMessage:
        role, message, center_json, places_json, created_at = row
        center = CenterOut(**json.loads(center_json)) if center_json else None
        places = [PlaceOut(**p) for p in json.loads(places_json)] if places_json else []
        return _to_message(role, message, center, places, created_at)

    def list(self, session_id):
        rows = self._query(
            "SELECT role, message, center_json, places_json, created_at FROM chat_message "
            "WHERE session_id=%s ORDER BY id ASC",
            (session_id,),
        )
        return [self._row_to_message(r) for r in rows]

    def last_assistant(self, session_id):
        rows = self._query(
            "SELECT role, message, center_json, places_json, created_at FROM chat_message "
            "WHERE session_id=%s AND role='assistant' AND places_json IS NOT NULL "
            "AND JSON_LENGTH(places_json) > 0 ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        return self._row_to_message(rows[0]) if rows else None

    def delete_expired(self, days=30):
        return self._execute("DELETE FROM chat_message WHERE created_at < NOW() - INTERVAL %s DAY", (days,))

    def delete_session(self, session_id):
        return self._execute("DELETE FROM chat_message WHERE session_id=%s", (session_id,))

    def ping(self):
        try:
            self._query("SELECT 1")
            return True
        except Exception:
            return False
