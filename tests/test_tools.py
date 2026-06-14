import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from tools import search_listings, suggest_outfit, create_fit_card, compare_price
from utils.data_loader import load_listings

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item.get("price", float('inf')) <= 10 for item in results)

def test_suggest_outfit_empty_wardrobe():
    # Handle empty wardrobe case
    new_item = {"title": "Cool jacket", "category": "outerwear", "description": "A very cool vintage jacket."}
    wardrobe = {"items": []}
    result = suggest_outfit(new_item, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Error" not in result

def test_suggest_outfit_normal():
    # Normal wardrobe case
    new_item = {"title": "Cool jacket", "category": "outerwear", "description": "A very cool vintage jacket."}
    wardrobe = {"items": [{"name": "Blue jeans", "category": "bottoms", "notes": "good"}]}
    result = suggest_outfit(new_item, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_empty_outfit():
    # Guard against an empty outfit string
    new_item = {"title": "Cool jacket", "price": 10, "platform": "depop"}
    result = create_fit_card("", new_item)
    assert "Error" in result

def test_create_fit_card_returns_result():
    new_item = {"title": "Cool jacket", "price": 10, "platform": "depop"}
    outfit = "Pair this with some blue jeans and a white tee."
    result1 = create_fit_card(outfit, new_item)
    result2 = create_fit_card(outfit, new_item)
    assert isinstance(result1, str)
    assert isinstance(result2, str)
    assert len(result1) > 0
    assert len(result2) > 0
    # Verify the outputs vary
    assert result1 != result2


# ── Stretch: compare_price ────────────────────────────────────────────────────

def test_compare_price_returns_expected_keys():
    listings = load_listings()
    result = compare_price(listings[0], listings)
    for key in ("verdict", "item_price", "median_price", "comparable_count", "explanation"):
        assert key in result

def test_compare_price_verdict_cheap_item():
    # Construct a fake item priced far below any real category median
    listings = load_listings()
    cheap_item = {"id": "fake-001", "category": "tops", "price": 1.0}
    result = compare_price(cheap_item, listings)
    assert result["verdict"] == "great deal"

def test_compare_price_verdict_expensive_item():
    listings = load_listings()
    expensive_item = {"id": "fake-002", "category": "tops", "price": 999.0}
    result = compare_price(expensive_item, listings)
    assert result["verdict"] == "above average"

def test_compare_price_no_comparables():
    # Category with no other items in the dataset
    listings = load_listings()
    unknown_item = {"id": "fake-003", "category": "hats", "price": 20.0}
    result = compare_price(unknown_item, listings)
    assert result["verdict"] == "unknown"
    assert result["comparable_count"] == 0

def test_agent_retry_removes_size_filter():
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe
    # Size "ZZZZ" doesn't exist — agent should retry without it and still find results
    session = run_agent("vintage graphic tee size ZZZZ under 50", get_example_wardrobe())
    assert session["error"] is None
    assert session["selected_item"] is not None
    assert any("size" in adj for adj in session["search_adjusted"])

def test_agent_price_comparison_populated():
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe
    session = run_agent("vintage graphic tee under 50", get_example_wardrobe())
    assert session["error"] is None
    pc = session["price_comparison"]
    assert pc is not None
    assert pc["verdict"] in ("great deal", "fair price", "slightly above average", "above average", "unknown")
