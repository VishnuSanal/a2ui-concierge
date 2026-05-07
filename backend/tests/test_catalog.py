import pytest
from concierge.catalog import load_catalog, search, get

def test_load_catalog_returns_at_least_25_items():
    catalog = load_catalog()
    assert len(catalog) >= 25

def test_search_filters_by_category():
    results = search(category="jewelry")
    assert len(results) >= 15
    assert all(p["category"] == "jewelry" for p in results)

def test_search_respects_price_max():
    results = search(price_max=100)
    assert all(p["price"] <= 100 for p in results)

def test_search_matches_any_vibe_tag():
    results = search(vibe_tags=["minimalist"])
    assert all("minimalist" in p["vibe_tags"] for p in results)

def test_get_returns_full_product():
    p = get("lum-jewel-001")
    assert p["id"] == "lum-jewel-001"
    assert "variants" in p

def test_get_unknown_id_raises():
    with pytest.raises(KeyError):
        get("does-not-exist")
