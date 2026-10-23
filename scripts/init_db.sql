-- 서울 여행 친구: 대화 기록 테이블 (기존 chat_history 테이블은 건드리지 않음)
-- 실행: docker exec -i seoul-tour-mysql mysql -u<USER> -p<PW> < scripts/init_db.sql
CREATE DATABASE IF NOT EXISTS seoul_tour DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE seoul_tour;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
