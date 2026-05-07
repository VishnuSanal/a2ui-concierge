import json
from pathlib import Path
from concierge import a2ui

FIX = Path(__file__).parent / "fixtures"

def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())

def test_chips_matches_fixture_shape():
    out = a2ui.chips(
        question="What does she lean toward?",
        options=[("jewelry", "Jewelry"), ("home", "Home"),
                 ("stationery", "Stationery"), ("skincare", "Skincare")],
    )
    fixture = _load("a2ui_chips.json")
    assert set(out.keys()) == set(fixture.keys())
    assert out["component"] == fixture["component"]

def test_products_carries_image_and_price():
    out = a2ui.products(
        reasoning="Three minimalist picks.",
        items=[
            {"id": "x", "name": "Thread Necklace", "price": 89,
             "image_url": "https://example.com/a.jpg", "why": "Warm tone."},
        ],
    )
    fixture = _load("a2ui_products.json")
    assert out["component"] == fixture["component"]
    assert out["items"][0]["price"] == 89

def test_product_detail_includes_variant_groups():
    out = a2ui.product_detail(
        product={"id": "x", "name": "Bar Pendant", "price": 124,
                 "image_url": "https://example.com/x.jpg"},
        variants={"finish": ["gold", "silver"], "length": ["16\"", "18\""]},
    )
    fixture = _load("a2ui_product_detail.json")
    assert set(out.keys()) == set(fixture.keys())
    assert out["component"] == fixture["component"]
    assert any(g["name"] == "finish" for g in out["variant_groups"])

def test_form_returns_fields():
    out = a2ui.form(fields=[
        {"type": "toggle", "name": "gift_wrap", "label": "Gift wrap"},
        {"type": "text", "name": "note", "label": "Note", "max_length": 120},
        {"type": "address", "name": "ship_to", "label": "Ship to"},
    ])
    assert len(out["fields"]) == 3

def test_confirmation_summarizes():
    out = a2ui.confirmation(
        order_id="A2UI-7741",
        line_items=[("Bar Pendant · Silver · 16\"", 124),
                    ("Gift wrap", 8)],
        total=132,
        ship_date="Mon, May 11",
    )
    assert out["order_id"] == "A2UI-7741"
    assert out["total"] == 132
