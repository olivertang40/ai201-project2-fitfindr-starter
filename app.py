"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of three strings:
            (listing_text, outfit_suggestion, fit_card)
        Each string maps to one of the three output panels in the UI.
    """
    # 1. Guard against an empty query and return an error message early.
    if not user_query or not user_query.strip():
        return "Error: Please enter a search query.", "", ""
        
    # 2. Select the wardrobe based on the user's radio button choice.
    if wardrobe_choice == "Example wardrobe":
        wardrobe = get_example_wardrobe()
    else:
        wardrobe = get_empty_wardrobe()
        
    # 3. Call the agent to run the full planning loop.
    session = run_agent(query=user_query, wardrobe=wardrobe)
    
    # 4. If the agent returned an error (e.g., no results), display it and halt.
    if session.get("error"):
        return session["error"], "", ""
        
    # 5. Format the top listing into a readable Markdown string for the UI.
    item = session["selected_item"]
    pc = session.get("price_comparison") or {}
    verdict_line = f"Price verdict: {pc.get('verdict', '—')} — {pc.get('explanation', '')}\n" if pc else ""

    adjusted = session.get("search_adjusted", [])
    adjusted_note = f"\n⚠️ Filters adjusted: {', '.join(adjusted)}.\n" if adjusted else ""

    listing_text = (
        f"{adjusted_note}"
        f"**{item.get('title')}**\n"
        f"Price: ${item.get('price'):.2f} | Size: {item.get('size')} | Platform: {item.get('platform')}\n"
        f"Condition: {item.get('condition')}\n"
        f"{verdict_line}\n"
        f"{item.get('description')}"
    )

    # Return the formatted listing, outfit suggestion, and fit card to the UI panels.
    return listing_text, session.get("outfit_suggestion", ""), session.get("fit_card", "")


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
