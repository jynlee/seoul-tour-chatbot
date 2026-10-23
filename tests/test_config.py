import pytest
from pydantic import ValidationError

from app.config import ConfigError, load_settings
from app.schemas import ChatRequest

REQUIRED = {
    "OPENSEARCH_USER": "admin",
    "OPENSEARCH_PASSWORD": "pw",
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "pw",
}


def test_missing_required_lists_all_names():
    with pytest.raises(ConfigError) as e:
        load_settings({"OPENSEARCH_USER": ""})
    msg = str(e.value)
    for name in ("OPENSEARCH_USER", "OPENSEARCH_PASSWORD", "MYSQL_USER", "MYSQL_PASSWORD"):
        assert name in msg


def test_defaults():
    s = load_settings(REQUIRED)
    assert s.opensearch_index == "seoul-tour-v2"
    assert s.ollama_model == "gemma4:e4b"
    assert s.mysql_db == "seoul_tour"
    assert s.opensearch_port == 9200
    assert s.mysql_port == 3306


def test_tour_key_only_requirement():
    s = load_settings({"TOUR_API_KEY": "k"}, required=("TOUR_API_KEY",))
    assert s.tour_api_key == "k"


def test_chat_request_rejects_blank():
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")
    with pytest.raises(ValidationError):
        ChatRequest(message="가" * 501)
    assert ChatRequest(message="  광화문 맛집  ").message == "광화문 맛집"
