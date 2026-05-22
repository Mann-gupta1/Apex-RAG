"""Strawberry schema introspection."""
from __future__ import annotations

from apex.api.graphql_schema import schema


def test_search_query_is_exposed():
    sdl = schema.as_str()
    assert "search(" in sdl
    assert "SearchPayload" in sdl


def test_submit_feedback_mutation_exposed():
    sdl = schema.as_str()
    assert "submitFeedback" in sdl


def test_chat_subscription_exposed():
    sdl = schema.as_str()
    assert "chatStream" in sdl


def test_enum_modality_exposed():
    sdl = schema.as_str()
    assert "enum Modality" in sdl
