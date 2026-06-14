"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re
from tools import search_listings, suggest_outfit, create_fit_card, compare_price
from utils.data_loader import load_listings


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "search_adjusted": [],       # filter(s) removed during retry, e.g. ["size 'M' removed"]
        "selected_item": None,       # top result, shared by Tools 2, 3, and 4
        "price_comparison": None,    # dict returned by compare_price (stretch)
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    # Step 2: Parse the user's query using simple Regex heuristics
    # Extract max_price (e.g., "under $30" or "under 30")
    max_price = None
    price_match = re.search(r'(?:under|<)\s*\$?(\d+(?:\.\d{2})?)', query, re.IGNORECASE)
    if price_match:
        max_price = float(price_match.group(1))
        query = query.replace(price_match.group(0), "")

    # Extract size (e.g., "size M" or "size XXS")
    size = None
    size_match = re.search(r'size\s+([a-zA-Z0-9/]+)', query, re.IGNORECASE)
    if size_match:
        size = size_match.group(1)
        query = query.replace(size_match.group(0), "")

    # The remaining text is the description (clean up punctuation)
    description = re.sub(r'[^\w\s]', '', query).strip()
    session["parsed"] = {"description": description, "size": size, "max_price": max_price}

    # Step 3: Call search_listings, then retry with loosened filters if empty
    results = search_listings(description=description, size=size, max_price=max_price)
    fallback_applied = []

    # Retry 1: remove size filter
    if not results and size is not None:
        retry = search_listings(description=description, size=None, max_price=max_price)
        if retry:
            results = retry
            fallback_applied.append(f"size filter '{size}' removed")

    # Retry 2: remove price filter (size already removed above)
    if not results and max_price is not None:
        retry = search_listings(description=description, size=None, max_price=None)
        if retry:
            results = retry
            fallback_applied.append(f"price filter '${max_price:.0f}' removed")

    session["search_results"] = results
    session["search_adjusted"] = fallback_applied

    if not results:
        session["error"] = (
            "We couldn't find any secondhand items matching your search criteria. "
            "Try different keywords, or remove size and price filters."
        )
        return session

    # Step 4: Select the top result
    selected_item = results[0]
    session["selected_item"] = selected_item

    # Step 4b: Compare price against comparable listings (stretch feature)
    session["price_comparison"] = compare_price(selected_item, load_listings())

    # Step 5: Call suggest_outfit
    outfit = suggest_outfit(selected_item, wardrobe)
    session["outfit_suggestion"] = outfit

    # Step 6: Call create_fit_card
    session["fit_card"] = create_fit_card(outfit, selected_item)

    # Step 7: Return the completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")

    print("\n\n=== Retry fallback path: impossible size, valid description ===\n")
    session3 = run_agent(
        query="vintage graphic tee size ZZZZ under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session3["error"]:
        print(f"Error: {session3['error']}")
    else:
        print(f"Found (after fallback): {session3['selected_item']['title']}")
        print(f"Filters adjusted: {session3['search_adjusted']}")
        pc = session3["price_comparison"]
        print(f"Price verdict: {pc['verdict']} — {pc['explanation']}")
