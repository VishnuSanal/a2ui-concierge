"""Tests for the v0.8 A2UI message builders in concierge.a2ui.

Every builder returns a list of v0.8 protocol messages — typically a
``surfaceUpdate`` followed by a ``beginRendering`` — wrapping a single
custom-catalog component as the root of a fresh surface. These tests
exercise the wire shape (envelope, BoundValue wrappers, component-type
keys, catalogId) and compare against the canonical fixtures.
"""
import json
from pathlib import Path
from concierge import a2ui

FIX = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def _surface_update(messages: list[dict]) -> dict:
    return next(m["surfaceUpdate"] for m in messages if "surfaceUpdate" in m)


def _begin(messages: list[dict]) -> dict:
    return next(m["beginRendering"] for m in messages if "beginRendering" in m)


def _root_component(messages: list[dict]) -> tuple[str, dict]:
    su = _surface_update(messages)
    begin = _begin(messages)
    root = next(c for c in su["components"] if c["id"] == begin["root"])
    [(component_type, props)] = root["component"].items()
    return component_type, props


def _assert_envelope(messages: list[dict], expected_type: str) -> None:
    """Every builder must emit a (surfaceUpdate, beginRendering) pair with
    matching surfaceId, a single root component of the expected type, and
    the custom catalog id."""
    assert len(messages) == 2
    su = _surface_update(messages)
    begin = _begin(messages)
    assert su["surfaceId"] == begin["surfaceId"]
    assert begin["catalogId"] == a2ui.CATALOG_ID
    assert begin["root"] in {c["id"] for c in su["components"]}
    component_type, _ = _root_component(messages)
    assert component_type == expected_type


def test_chips_wraps_in_surface_update_with_chip_group():
    messages = a2ui.chips(
        question="What does she lean toward?",
        options=[("jewelry", "Jewelry"), ("home", "Home"),
                 ("stationery", "Stationery"), ("skincare", "Skincare")],
    )
    _assert_envelope(messages, "ChipGroup")
    _, props = _root_component(messages)
    assert props["question"] == {"literalString": "What does she lean toward?"}
    assert props["maxAllowedSelections"] == 1
    assert props["variant"] == "chips"
    assert props["selections"] == {"literalArray": []}
    assert props["options"][0] == {"value": "jewelry", "label": {"literalString": "Jewelry"}}
    assert props["action"]["name"] == "chip-group"


def test_chips_matches_fixture():
    messages = a2ui.chips(
        question="What does she lean toward?",
        options=[("jewelry", "Jewelry"), ("home", "Home"),
                 ("stationery", "Stationery"), ("skincare", "Skincare")],
    )
    # Compare component-type and prop shape — surfaceIds are random.
    type_, props = _root_component(messages)
    fixture = _load("a2ui_chips.json")
    fx_type, fx_props = next(iter(fixture["root"]["component"].items()))
    assert type_ == fx_type
    assert props["question"] == fx_props["question"]
    assert props["options"] == fx_props["options"]


def test_products_carries_image_and_price():
    messages = a2ui.products(
        reasoning="Three minimalist picks.",
        items=[
            {"id": "x", "name": "Thread Necklace", "price": 89,
             "image_url": "https://example.com/a.jpg", "why": "Warm tone."},
        ],
    )
    _assert_envelope(messages, "CardGrid")
    _, props = _root_component(messages)
    assert props["reasoning"] == {"literalString": "Three minimalist picks."}
    assert props["items"][0]["price"] == 89
    assert props["items"][0]["imageUrl"] == "https://example.com/a.jpg"


def test_product_detail_includes_variant_groups():
    messages = a2ui.product_detail(
        product={"id": "x", "name": "Bar Pendant", "price": 124,
                 "image_url": "https://example.com/x.jpg"},
        variants={"finish": ["gold", "silver"], "length": ["16\"", "18\""]},
    )
    _assert_envelope(messages, "ProductDetail")
    _, props = _root_component(messages)
    assert props["product"]["name"] == "Bar Pendant"
    assert props["product"]["imageUrl"] == "https://example.com/x.jpg"
    assert any(g["name"] == "finish" for g in props["variantGroups"])


def test_form_returns_fields_with_bound_labels():
    messages = a2ui.form(fields=[
        {"type": "toggle", "name": "gift_wrap", "label": "Gift wrap"},
        {"type": "text", "name": "note", "label": "Note", "max_length": 120},
        {"type": "address", "name": "ship_to", "label": "Ship to"},
    ])
    _assert_envelope(messages, "ConciergeForm")
    _, props = _root_component(messages)
    assert len(props["fields"]) == 3
    note_field = next(f for f in props["fields"] if f["name"] == "note")
    assert note_field["maxLength"] == 120
    assert note_field["label"] == {"literalString": "Note"}


def test_confirmation_summarizes():
    messages = a2ui.confirmation(
        order_id="A2UI-7741",
        line_items=[("Bar Pendant · Silver · 16\"", 124),
                    ("Gift wrap", 8)],
        total=132,
        ship_date="Mon, May 11",
    )
    _assert_envelope(messages, "ConfirmationCard")
    _, props = _root_component(messages)
    assert props["orderId"] == "A2UI-7741"
    assert props["total"] == 132
    assert props["shipDate"] == {"literalString": "Mon, May 11"}


def test_begin_rendering_references_a_known_root():
    """Defensive: catch builders that mismatch root id and component id."""
    for messages in [
        a2ui.chips(question="?", options=[("a", "A")]),
        a2ui.products(reasoning="r", items=[]),
        a2ui.confirmation(order_id="A", line_items=[], total=0, ship_date=""),
    ]:
        su = _surface_update(messages)
        begin = _begin(messages)
        ids = {c["id"] for c in su["components"]}
        assert begin["root"] in ids
        assert begin["surfaceId"] == su["surfaceId"]
