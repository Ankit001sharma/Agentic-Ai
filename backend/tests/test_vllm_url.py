"""Tests for OpenAI-compatible base URL normalization."""

from app.llm.vllm_url import normalize_openai_compatible_base


def test_normalize_strips_chat_completions_path():
    assert (
        normalize_openai_compatible_base("https://miniorangeai.miniorange.in/v1/chat/completions")
        == "https://miniorangeai.miniorange.in"
    )


def test_normalize_preserves_http_port():
    assert (
        normalize_openai_compatible_base("http://miniorangeai.miniorange.in:8000/v1/chat/completions")
        == "http://miniorangeai.miniorange.in:8000"
    )


def test_normalize_idempotent_on_host_only():
    assert normalize_openai_compatible_base("https://example.com") == "https://example.com"


def test_normalize_strips_trailing_v1():
    assert normalize_openai_compatible_base("https://example.com/v1") == "https://example.com"
