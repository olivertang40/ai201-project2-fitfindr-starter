import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from tools import search_listings, suggest_outfit, create_fit_card

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
