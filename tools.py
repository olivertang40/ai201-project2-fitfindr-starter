"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    # 1. Load all listings with load_listings()
    listings = load_listings()
    filtered_listings = []

    # 2. Filter by max_price and size (if provided)
    for item in listings:
        if max_price is not None and item.get("price", float('inf')) > max_price:
            continue
        
        if size is not None:
            item_size = item.get("size", "").lower()
            if size.lower() not in item_size:
                continue
                
        filtered_listings.append(item)

    # 3. Score each remaining listing by keyword overlap with `description`
    scored_items = []
    # Split description into lowercase keywords
    keywords = set(description.lower().split())
    
    for item in filtered_listings:
        # Combine title, description, and style tags into one searchable string
        item_text = f"{item.get('title', '')} {item.get('description', '')} {' '.join(item.get('style_tags', []))}".lower()
        
        score = sum(1 for word in keywords if word in item_text)
        
        # 4. Drop any listings with a score of 0
        if score > 0:
            scored_items.append((score, item))

    # 5. Sort by score, highest first, and return the listing dicts
    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored_items]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()
    
    # 格式化新衣服的信息，供大模型阅读
    item_desc = f"{new_item.get('title')} ({new_item.get('category')}): {new_item.get('description')}"
    
    # 1. Check whether wardrobe['items'] is empty.
    wardrobe_items = wardrobe.get("items", [])
    
    if not wardrobe_items:
        # 2. If empty: call the LLM with a prompt for general styling ideas
        prompt = (
            f"I am considering buying this secondhand item: {item_desc}.\n"
            "I don't have a specific wardrobe right now. "
            "Can you give me 1-2 general styling ideas or outfit combinations for this item? "
            "Keep it concise, trendy, and helpful. No pleasantries, just the styling advice."
        )
    else:
        # 3. If not empty: format the wardrobe items and ask for specific combinations
        wardrobe_desc = "\n".join([f"- {w.get('name')} ({w.get('category')}): {w.get('notes', '')}" for w in wardrobe_items])
        prompt = (
            f"I am considering buying this secondhand item: {item_desc}.\n"
            f"Here is my current wardrobe:\n{wardrobe_desc}\n\n"
            "Can you suggest 1-2 specific outfit combinations using the new item and pieces from my existing wardrobe? "
            "Make sure to specifically name the items from my wardrobe. "
            "Keep it concise, personalized, and trendy. No pleasantries, just the styling advice."
        )
        
    # 4. Return the LLM's response as a string
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful and trendy virtual personal stylist."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile", # 使用 Groq 的高性能模型
            temperature=0.7, # 增加一点创造性
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Styling advice is currently unavailable. (Error: {str(e)})"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # 1. Guard against an empty or whitespace-only outfit string.
    if not outfit or not outfit.strip():
        return "Error: Cannot generate a fit card without outfit styling advice."
        
    client = _get_groq_client()
    
    # Extract item details safely
    title = new_item.get("title", "this item")
    price = new_item.get("price", "a great deal")
    platform = new_item.get("platform", "a thrift store")
    
    # 2. Build a prompt
    prompt = (
        f"Write a short, trendy, and shareable social media caption (like for Instagram or TikTok) for this OOTD (Outfit of the Day).\n\n"
        f"The highlighted secondhand find is: '{title}' thrifted for ${price} off {platform}.\n"
        f"The outfit styling is: {outfit}\n\n"
        "Guidelines:\n"
        "- Keep it 2-4 sentences max.\n"
        "- Feel casual, authentic, and trendy (like a real Gen Z OOTD post, no cringe corporate speak).\n"
        "- Mention the item name, its price, and the platform naturally (once each).\n"
        "- Capture the overall outfit vibe.\n"
        "- No pleasantries or hashtags at the start, just give me the raw caption."
    )
    
    # 3. Call the LLM and return the response.
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a Gen-Z fashion influencer writing authentic social media captions."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.85, # 较高的温度值，让文案更加灵活有创意
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Fit card generation is currently unavailable. (Error: {str(e)})"


# ── Tool 4: compare_price (stretch feature) ───────────────────────────────────

def compare_price(item: dict, all_listings: list[dict]) -> dict:
    """
    Compare item price against other listings in the same category.
    Pure Python — no LLM call.

    Args:
        item:         The listing dict of the item to evaluate.
        all_listings: Full listings dataset from load_listings().

    Returns:
        A dict with keys:
            verdict (str):          "great deal" | "fair price" |
                                    "slightly above average" | "above average" | "unknown"
            item_price (float):     The item's price.
            median_price (float):   Median price of comparable items, or None.
            comparable_count (int): Number of items used for comparison.
            explanation (str):      One human-readable sentence summarising the verdict.
        Never raises an exception.
    """
    category = item.get("category")
    item_price = item.get("price", 0.0)
    item_id = item.get("id")

    comparables = [
        l for l in all_listings
        if l.get("category") == category and l.get("id") != item_id
    ]

    if not comparables:
        return {
            "verdict": "unknown",
            "item_price": item_price,
            "median_price": None,
            "comparable_count": 0,
            "explanation": f"No other {category} items found to compare against.",
        }

    prices = sorted(l.get("price", 0.0) for l in comparables)
    median = prices[len(prices) // 2]

    ratio = item_price / median if median > 0 else 1.0
    if ratio <= 0.75:
        verdict = "great deal"
    elif ratio <= 1.0:
        verdict = "fair price"
    elif ratio <= 1.3:
        verdict = "slightly above average"
    else:
        verdict = "above average"

    return {
        "verdict": verdict,
        "item_price": item_price,
        "median_price": round(median, 2),
        "comparable_count": len(comparables),
        "explanation": (
            f"Among {len(comparables)} comparable {category} items, "
            f"the median price is ${median:.2f}. "
            f"At ${item_price:.2f}, this item is a {verdict}."
        ),
    }
