restaurant_bot/
│
├── app.py              # Main LangGraph agent logic and interactive CLI loop
├── README.md           # Project documentation and setup guide
└── requirements.txt    # Python dependencies

# AI Restaurant Lifecycle Agent (LangGraph)

An autonomous restaurant ordering and lifecycle management agent built with **LangGraph**. It manages customer orders from intake to table delivery, enforcing inventory tracking, intent filtering, human-in-the-loop retries, cooking failures, and delivery re-attempts without requiring any external paid API keys.

---

## Features

- **Query Filtering:** Rejects off-topic, non-food requests immediately before running order logic.
- **Stock & Menu Tracking:** Validates item availability and deducts stock in real time upon successful confirmation.
- **Dynamic Alternative Suggestions:** Recommends in-stock alternatives from the same category when items are unavailable.
- **Human-in-the-Loop Interaction:** Uses LangGraph `interrupt` and `Command(resume=...)` to pause and ask the user for clarification in real-time.
- **Retry Limiting:** Automatically cancels orders after 3 failed attempts.
- **Lifecycle Failure Recovery:** 
  - Simulates cooking incidents and escalates to human managers.
  - Simulates delivery mishaps (dropped tray) and automatically routes the meal back to the kitchen to re-cook.
- **Thread-Scoped State Management:** Powered by `MemorySaver` to persist state across multi-turn interactions.
- **100% Free & Local:** Runs completely on Python rule-based logic without OpenAI, Anthropic, or Gemini tokens.

---

## State Architecture

