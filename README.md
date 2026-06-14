# FitFindr

A secondhand fashion agent that finds thrifted clothing items, generates personalized outfit suggestions based on your existing wardrobe, and produces a shareable social media fit card — all from a single natural language query.

Built with Python, Groq (LLaMA 3.3-70b), and Gradio.

---

## Quick Start

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:
```
GROQ_API_KEY=your_key_here
```
Get a free key at [console.groq.com](https://console.groq.com).

Run the app:
```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

Run the test suite:
```bash
pytest tests/
```

---

## Tool Inventory

### Tool 1 — `search_listings(description, size, max_price)`

**Purpose:** Searches the mock secondhand database for items matching a natural language description, with optional size and price filters. This is a pure Python function — no LLM call.

| Parameter | Type | Description |
|---|---|---|
| `description` | `str` | Keywords describing the item (e.g., `"vintage graphic tee"`) |
| `size` | `str \| None` | Size filter, case-insensitive substring match (e.g., `"M"` matches `"S/M"`). Pass `None` to skip. |
| `max_price` | `float \| None` | Maximum price ceiling, inclusive. Pass `None` to skip. |

**Returns:** `list[dict]` — matching listings sorted by keyword relevance score (highest first). Empty list `[]` if nothing matches. Never raises an exception.

Each result dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.

---

### Tool 2 — `suggest_outfit(new_item, wardrobe)`

**Purpose:** Calls the LLM to suggest 1–2 complete outfit combinations using the new thrifted item and pieces from the user's existing wardrobe. Handles the empty wardrobe case gracefully.

| Parameter | Type | Description |
|---|---|---|
| `new_item` | `dict` | A listing dict from `search_listings` — the item the user is considering buying |
| `wardrobe` | `dict` | A wardrobe dict with an `'items'` key containing a list of clothing pieces. May be empty. |

**Returns:** `str` — non-empty string with personalized outfit suggestions. If the wardrobe is empty, returns general styling advice for the new item instead of specific pairings.

---

### Tool 3 — `create_fit_card(outfit, new_item)`

**Purpose:** Calls the LLM to generate a short, casual social media caption (Instagram/TikTok style) for the outfit. Uses a higher LLM temperature to produce varied, authentic-sounding output.

| Parameter | Type | Description |
|---|---|---|
| `outfit` | `str` | The styling suggestion string returned by `suggest_outfit` |
| `new_item` | `dict` | The listing dict for the thrifted item |

**Returns:** `str` — 2–4 sentence caption mentioning the item name, price, and platform naturally. If `outfit` is empty or whitespace-only, returns a descriptive error message string instead of raising an exception.

---

## Planning Loop

The agent runs a **sequential, conditional workflow** — it does not retry failed steps, and it halts early rather than passing empty data downstream.

```
User Query
    │
    ▼
1. Parse query (regex) → extract description, size, max_price
    │
    ▼
2. search_listings(description, size, max_price)
    │
    ├── empty list ──→ set session["error"], return early (skip steps 3–4)
    │
    └── results found
          │
          ▼
3. suggest_outfit(results[0], wardrobe)
          │
          ▼
4. create_fit_card(outfit_suggestion, results[0])
          │
          ▼
     Return session dict
```

**Decision point:** The only branching decision the agent makes is after step 2. If `search_listings` returns an empty list, the agent sets a user-facing error message in `session["error"]` and returns immediately — it never calls `suggest_outfit` with empty input, which would produce meaningless output. If results are found, it always selects the top-ranked result (index 0) and proceeds unconditionally through steps 3 and 4.

**Query parsing** uses regex heuristics rather than an LLM call, keeping the agent fast and deterministic for this step:
- Price: matches patterns like `"under $30"` or `"under 30"` → `max_price = 30.0`
- Size: matches `"size M"` or `"size XXS"` → `size = "M"`
- Description: whatever remains after removing the matched price/size tokens

---

## State Management

All state for one interaction lives in a single `session` dictionary, initialized by `_new_session()` and passed through every step:

```python
session = {
    "query":             "vintage graphic tee under $30",  # original input
    "parsed":            {"description": "...", "size": None, "max_price": 30.0},
    "search_results":    [...],          # full results list from Tool 1
    "selected_item":     {...},          # results[0], shared by Tools 2 and 3
    "wardrobe":          {...},          # user's wardrobe, passed to Tool 2
    "outfit_suggestion": "...",          # string from Tool 2, passed into Tool 3
    "fit_card":          "...",          # final output string from Tool 3
    "error":             None,           # set on early halt, None on success
}
```

Each tool reads its inputs from session keys populated by the previous step and writes its output to a new key. No tool re-reads the raw query or calls earlier tools — the session dict is the single source of truth.

**State flow between tools:**
- `search_listings` → writes to `session["search_results"]`; `results[0]` is saved to `session["selected_item"]`
- `suggest_outfit` reads `session["selected_item"]` and `session["wardrobe"]` → writes to `session["outfit_suggestion"]`
- `create_fit_card` reads `session["outfit_suggestion"]` and `session["selected_item"]` → writes to `session["fit_card"]`

---

## Error Handling

### Tool 1: `search_listings` — No Results

**Failure mode:** The query is too specific, the price ceiling is too low, or the size doesn't exist in the dataset.

**Behavior:** Returns `[]`. The agent detects this in `run_agent()` after the call:
```python
if not results:
    session["error"] = "We couldn't find any secondhand items matching your search criteria. Try removing the price or size filters, or use different keywords."
    return session
```
Tools 2 and 3 are never called.

**Concrete example from testing:**
```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
# Output: []

python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe
s = run_agent('designer ballgown size XXS under 5', get_example_wardrobe())
print(s['error'])
# Output: We couldn't find any secondhand items matching your search criteria.
#         Try removing the price or size filters, or use different keywords.
"
```

---

### Tool 2: `suggest_outfit` — Empty Wardrobe

**Failure mode:** User is new and hasn't set up a wardrobe yet (`wardrobe["items"] == []`).

**Behavior:** Instead of producing an error, the tool detects the empty list and builds a different prompt — asking the LLM for general styling advice rather than specific pairings with named wardrobe pieces:
```python
if not wardrobe_items:
    prompt = "I don't have a specific wardrobe right now. Can you give me 1-2 general styling ideas..."
```

**Concrete example from testing:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
# Output: 'Pair the Y2K baby tee with high-waisted mom jeans and chunky sneakers
#          for a retro-inspired casual look...'
# Returns useful advice, no exception, no empty string.
"
```

---

### Tool 3: `create_fit_card` — Empty Outfit String

**Failure mode:** `outfit` is empty or whitespace-only (e.g., if `suggest_outfit` somehow returned `""`).

**Behavior:** Guards at the top of the function before any LLM call:
```python
if not outfit or not outfit.strip():
    return "Error: Cannot generate a fit card without outfit styling advice."
```

**Concrete example from testing:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
# Output: 'Error: Cannot generate a fit card without outfit styling advice.'
# Returns a string, not a Python exception.
"
```

---

## Running the Tests

```bash
pytest tests/ -v
```

Expected output:
```
tests/test_tools.py::test_search_returns_results         PASSED
tests/test_tools.py::test_search_empty_results           PASSED
tests/test_tools.py::test_search_price_filter            PASSED
tests/test_tools.py::test_suggest_outfit_empty_wardrobe  PASSED
tests/test_tools.py::test_suggest_outfit_normal          PASSED
tests/test_tools.py::test_create_fit_card_empty_outfit   PASSED
tests/test_tools.py::test_create_fit_card_returns_result PASSED

7 passed
```

---

## AI Tool Usage

### Instance 1 — Implementing `tools.py` (Gemini Code Assist + Claude Code)

**Input given to AI:**
- The full "Tools" section from `planning.md` — inputs, return types, and failure modes for all three tools
- The `listings.json` schema (field names and types)
- The `wardrobe_schema.json` structure
- The instruction: implement each function as a standalone, testable unit

**What it produced:**
A first draft of `search_listings` using a simple `in` check for keywords and a single combined filter loop. The initial `suggest_outfit` had no empty-wardrobe branch — it would crash if `wardrobe["items"]` was empty.

**What I changed before using it:**
1. Added the `if not wardrobe_items:` branch to `suggest_outfit` with a distinct general-styling prompt — this was the most important correction, as the spec explicitly required graceful degradation.
2. Changed the keyword scoring in `search_listings` from a naive `in` check on just the title to a combined search across `title + description + style_tags`, which dramatically improved relevance for multi-word queries.
3. Added the `if score > 0: drop` guard so listings with zero keyword overlap don't appear in results at all.

---

### Instance 2 — Implementing `run_agent()` in `agent.py` (Claude Code)

**Input given to AI:**
- The "Planning Loop" section of `planning.md` describing the conditional sequence
- The "State Management" section describing the `session` dict and what each key holds
- The Mermaid architecture flowchart from `planning.md`
- The `_new_session()` scaffold already in the file

**What it produced:**
A working implementation of `run_agent()` with regex parsing for price and size, correct early-halt logic on empty results, and all session keys populated in order.

**What I changed before using it:**
1. The initial regex for price extraction left the matched token in the `query` string, so `description` still contained the phrase `"under $30"`. Added `query = query.replace(price_match.group(0), "")` and the same for size — this was needed so the description passed to `search_listings` was clean keywords only.
2. Adjusted the description cleanup regex from `.strip()` alone to `re.sub(r'[^\w\s]', '', query).strip()` to remove residual punctuation after stripping the price and size tokens.

---

## Spec Reflection

The most valuable part of writing `planning.md` before coding was being forced to define the failure modes in the error handling table first. When I reached Tool 2 implementation, the spec already said *"if the wardrobe is empty, generate general styling advice"* — so the code path was obvious. Without the spec, the natural instinct would have been to add a guard and return an error, which is worse UX.

The part of the spec that needed the most revision during implementation was the query parsing strategy. The planning doc described regex extraction at a high level, but the edge case where extracted tokens had to be removed from the description string before scoring wasn't anticipated — that gap only appeared when testing with queries that contained both a price and a size filter.

The Mermaid architecture diagram was the most useful artifact to hand to an AI tool: it made the conditional structure explicit in a way that plain prose doesn't, and the AI-generated planning loop code matched the diagram's branching logic almost exactly on the first attempt.

---

## Project Structure

```
fitfindr/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe (10 items)
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tests/
│   └── test_tools.py          # 7 pytest cases covering all tools and failure modes
├── tools.py                   # search_listings, suggest_outfit, create_fit_card
├── agent.py                   # run_agent() — the planning loop
├── app.py                     # Gradio UI — handle_query() wires agent to interface
├── planning.md                # Spec: tools, loop design, state, error handling, architecture
├── pytest.ini                 # pythonpath config for test imports
└── requirements.txt           # groq, python-dotenv, gradio, pytest
```
