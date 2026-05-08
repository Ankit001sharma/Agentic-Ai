from __future__ import annotations

from app.tools.miniorange_tool import _extract_query_arg


def test_extract_query_arg_from_primary_field() -> None:
    assert _extract_query_arg({"query": "  miniorange saml  "}) == "miniorange saml"


def test_extract_query_arg_from_alias_fields() -> None:
    assert _extract_query_arg({"text": "joomla sso"}) == "joomla sso"
    assert _extract_query_arg({"prompt": "wordpress oauth"}) == "wordpress oauth"
    assert _extract_query_arg({"question": "drupal saml setup"}) == "drupal saml setup"


def test_extract_query_arg_from_nested_arguments_shape() -> None:
    args = {"arguments": {"query": "miniOrange plugins list"}}
    assert _extract_query_arg(args) == "miniOrange plugins list"
