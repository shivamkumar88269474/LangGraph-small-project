
import random
from typing import TypedDict, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

# --- 1. Menu and Inventory ---
MENU: Dict[str, Dict[str, Any]] = {
    "burger": {"price": 10.99, "stock": 5, "category": "mains"},
    "pizza": {"price": 14.99, "stock": 2, "category": "mains"},
    "pasta": {"price": 12.50, "stock": 0, "category": "mains"},  # Out of stock
    "fries": {"price": 4.50, "stock": 10, "category": "sides"},
    "salad": {"price": 6.00, "stock": 4, "category": "sides"}
}

FOOD_KEYWORDS = set(MENU.keys()).union({
    "food", "order", "eat", "drink", "hungry", "menu", "dish", "meal", "buy"
})


# --- 2. Memory Board (State) ---
class RestaurantState(TypedDict):
    query: str
    dish: Optional[str]
    quantity: int
    price: float
    order_attempts: int
    delivery_attempts: int
    status: str
    feedback_message: str
    is_food_query: bool


# --- 3. The Action Steps (Nodes) ---

def filter_query_node(state: RestaurantState) -> RestaurantState:
    query = state["query"].lower()
    is_food = any(word in query for word in FOOD_KEYWORDS)
    
    if not is_food:
        return {
            **state,
            "is_food_query": False,
            "status": "rejected",
            "feedback_message": "Query rejected: Only food and dining orders are supported."
        }
    return {**state, "is_food_query": True, "status": "query_accepted"}


def take_order_node(state: RestaurantState) -> RestaurantState:
    query = state["query"].lower()
    attempts = state.get("order_attempts", 0) + 1

    matched_item = None
    for item in MENU.keys():
        if item in query:
            matched_item = item
            break

    qty = 1
    for token in query.split():
        if token.isdigit():
            qty = int(token)
            break

    # Item not on the menu
    if not matched_item:
        if attempts >= 3:
            return {
                **state,
                "order_attempts": attempts,
                "status": "cancelled",
                "feedback_message": "Maximum attempts reached (3/3). Order cancelled."
            }

        available_items = [name for name, d in MENU.items() if d["stock"] > 0]
        prompt = (
            f"Item not found. Available dishes: {', '.join(available_items)}. "
            f"Attempt {attempts}/3. What would you like instead?"
        )
        user_response = interrupt(prompt)
        return {
            **state,
            "query": user_response,
            "order_attempts": attempts,
            "status": "order_retrying"
        }

    # Item is out of stock or low stock
    available_stock = MENU[matched_item]["stock"]
    if available_stock < qty:
        if attempts >= 3:
            return {
                **state,
                "order_attempts": attempts,
                "status": "cancelled",
                "feedback_message": "Maximum attempts reached (3/3). Order cancelled."
            }

        category = MENU[matched_item]["category"]
        alts = [
            f"{k} ({v['stock']} left)"
            for k, v in MENU.items()
            if v["category"] == category and v["stock"] > 0 and k != matched_item
        ]
        prompt = (
            f"Insufficient stock for '{matched_item}' (Available: {available_stock}). "
            f"Alternative {category}: {', '.join(alts) if alts else 'None'}. "
            f"Attempt {attempts}/3. What would you like instead?"
        )
        user_response = interrupt(prompt)
        return {
            **state,
            "query": user_response,
            "order_attempts": attempts,
            "status": "order_retrying"
        }

    # Order accepted
    MENU[matched_item]["stock"] -= qty
    unit_price = MENU[matched_item]["price"]
    
    return {
        **state,
        "dish": matched_item,
        "quantity": qty,
        "price": round(unit_price * qty, 2),
        "order_attempts": attempts,
        "status": "order_confirmed",
        "feedback_message": f"Confirmed: {qty}x {matched_item} (${unit_price * qty:.2f})."
    }


def cook_node(state: RestaurantState) -> RestaurantState:
    kitchen_accident = random.random() < 0.10
    if kitchen_accident:
        return {
            **state,
            "status": "kitchen_error",
            "feedback_message": f"ALERT: Kitchen incident on {state['dish']}. Escalated to manager."
        }
    return {
        **state,
        "status": "cooked",
        "feedback_message": f"{state['quantity']}x {state['dish']} prepared."
    }


def serve_node(state: RestaurantState) -> RestaurantState:
    delivery_attempts = state.get("delivery_attempts", 0) + 1
    dropped = random.random() < 0.25
    
    if dropped and delivery_attempts <= 2:
        return {
            **state,
            "delivery_attempts": delivery_attempts,
            "status": "delivery_failed",
            "feedback_message": f"Delivery attempt #{delivery_attempts} failed. Re-cooking..."
        }
    
    return {
        **state,
        "delivery_attempts": delivery_attempts,
        "status": "delivered",
        "feedback_message": f"Successfully delivered {state['quantity']}x {state['dish']}!"
    }


# --- 4. Flow Rules ---

def route_after_filter(state: RestaurantState) -> str:
    return "take_order" if state["is_food_query"] else END


def route_after_order(state: RestaurantState) -> str:
    if state["status"] == "order_confirmed":
        return "cook"
    if state["status"] == "order_retrying":
        return "take_order"
    return END


def route_after_cook(state: RestaurantState) -> str:
    return END if state["status"] == "kitchen_error" else "serve"


def route_after_serve(state: RestaurantState) -> str:
    return "cook" if state["status"] == "delivery_failed" else END


# --- 5. Build the LangGraph Engine ---

workflow = StateGraph(RestaurantState)
workflow.add_node("filter_query", filter_query_node)
workflow.add_node("take_order", take_order_node)
workflow.add_node("cook", cook_node)
workflow.add_node("serve", serve_node)

workflow.set_entry_point("filter_query")
workflow.add_conditional_edges("filter_query", route_after_filter)
workflow.add_conditional_edges("take_order", route_after_order)
workflow.add_conditional_edges("cook", route_after_cook)
workflow.add_conditional_edges("serve", route_after_serve)

checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)


# --- 6. Live Interactive Terminal Loop ---

def run_interactive_session(user_initial_query: str, thread_id: str = "customer-101"):
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "query": user_initial_query,
        "dish": None,
        "quantity": 0,
        "price": 0.0,
        "order_attempts": 0,
        "delivery_attempts": 0,
        "status": "new",
        "feedback_message": "",
        "is_food_query": False
    }

    print(f"\n--- New Order Started (Thread {thread_id}) ---")
    current_input: Any = initial_state

    while True:
        for _ in app.stream(current_input, config=config, stream_mode="values"):
            pass

        state_snapshot = app.get_state(config)

        if state_snapshot.tasks and any(t.interrupts for t in state_snapshot.tasks):
            interrupt_payload = state_snapshot.tasks[0].interrupts[0].value
            print(f"\n[Agent]: {interrupt_payload}")
            user_text = input("[You]: ")
            current_input = Command(resume=user_text)
        else:
            final_state = state_snapshot.values
            print(f"\n[Agent]: {final_state.get('feedback_message')}")
            print(f"Final Status: {final_state.get('status')}")
            break


# --- 7. Run Directly ---
if __name__ == "__main__":
    run_interactive_session("I would like 2 pasta please")
