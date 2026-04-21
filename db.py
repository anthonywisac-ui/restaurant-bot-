# db.py - In-memory storage and shared database operations
import time
from config import GOOGLE_SHEET_WEBHOOK
import aiohttp

# Global dictionaries
customer_sessions = {}
last_message_time = {}
saved_orders = {}
customer_order_lookup = {}
manager_pending = {}
customer_profiles = {}

# ========== Shared functions (moved from flow.py) ==========
def save_profile(sender, session):
    if session.get("name"):
        profile = customer_profiles.get(sender, {"order_history": []})
        profile.update({
            "name": session.get("name", ""),
            "address": session.get("address", ""),
            "lang": session.get("lang", "en"),
            "delivery_type": session.get("delivery_type", ""),
            "payment": session.get("payment", ""),
        })
        if "order_history" not in profile:
            profile["order_history"] = []
        customer_profiles[sender] = profile

def add_to_order_history(sender, order_id, order_items):
    profile = customer_profiles.get(sender, {"order_history": []})
    if "order_history" not in profile:
        profile["order_history"] = []
    profile["order_history"].append({
        "order_id": order_id,
        "items": [
            {"item_id": k, "name": v["item"]["name"], "qty": v["qty"]}
            for k, v in order_items.items()
        ],
        "timestamp": time.time()
    })
    profile["order_history"] = profile["order_history"][-5:]
    customer_profiles[sender] = profile

def get_favorite_items(sender):
    profile = customer_profiles.get(sender, {})
    history = profile.get("order_history", [])
    if not history:
        return []
    item_counts = {}
    for order in history:
        for item in order.get("items", []):
            name = item.get("name") if isinstance(item, dict) else item
            if name:
                item_counts[name] = item_counts.get(name, 0) + 1
    sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
    return [item for item, count in sorted_items[:3]]

async def save_to_sheet(customer_number, session, order_id):
    from utils import get_order_total, get_delivery_fee
    order = session.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = get_delivery_fee(total, session.get("delivery_type"))
    grand_total = total + tax + delivery_charge
    items_list = [f"{v['item']['name']} x{v['qty']}" for v in order.values()]
    data = {
        "order_id": str(order_id),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": session.get("name", ""),
        "customer_number": f"+{customer_number}",
        "items": ", ".join(items_list),
        "subtotal": round(total, 2),
        "tax": round(tax, 2),
        "delivery_charge": round(delivery_charge, 2),
        "grand_total": round(grand_total, 2),
        "delivery_type": session.get("delivery_type", ""),
        "address": session.get("address", ""),
        "payment": session.get("payment", ""),
        "language": session.get("lang", "en"),
        "status": "New"
    }
    saved_orders[order_id] = {**data, "timestamp": time.time()}
    customer_order_lookup.setdefault(customer_number, []).append(order_id)
    customer_order_lookup[customer_number] = customer_order_lookup[customer_number][-10:]
    manager_pending[order_id] = customer_number
    print(f"Order #{order_id} linked to customer {customer_number}")
    if GOOGLE_SHEET_WEBHOOK:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(GOOGLE_SHEET_WEBHOOK, json=data) as r:
                    print(f"Sheet saved: {r.status}")
        except Exception as e:
            print(f"Sheet error: {e}")
    else:
        print(f"Order saved locally: #{order_id}")