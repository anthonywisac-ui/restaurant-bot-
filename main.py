import os
import re
import aiohttp
import traceback
import random
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, HTMLResponse
import uvicorn

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"Token: {WHATSAPP_TOKEN[:20] if WHATSAPP_TOKEN else 'MISSING'}...")
print(f"Phone ID: {WHATSAPP_PHONE_NUMBER_ID}")

# ----------------------------
# SESSION STORE (in-memory)
# ----------------------------
customer_sessions = {}

def new_session():
    return {
        "stage": "ai_chat",
        "order": {},              # {item_id: {"item": {...}, "qty": int}}
        "delivery_type": "",
        "address": "",
        "name": "",
        "payment": "",
        "last_added": None,
        "current_cat": None,
        "pending_combo": [],
        "conversation": [],
        "upsell_declined": False, # once they decline, reduce upsells
    }

def get_session(sender):
    if sender not in customer_sessions:
        customer_sessions[sender] = new_session()
    return customer_sessions[sender]

# ----------------------------
# MENU (Wild Bites)
# ----------------------------
MENU = {
    "deals": {
        "name": "🔥 Deals (Best Value)",
        "items": {
            "DL1": {"name": "Burger Combo Add-on", "price": 4.99, "emoji": "🔥", "desc": "Add fries + soda to any burger"},
            "DL2": {"name": "Double Smash Meal Deal", "price": 18.99, "emoji": "🍔", "desc": "Smash burger + fries + soda"},
            "DL3": {"name": "Pizza + Wings Deal", "price": 21.99, "emoji": "🍕", "desc": "Any 12” pizza + 6 wings"},
            "DL4": {"name": "Family Pizza Deal", "price": 29.99, "emoji": "👨‍👩‍👧‍👦", "desc": "2 pizzas + 2 sodas"},
            "DL5": {"name": "Ribs Night Deal", "price": 21.99, "emoji": "🍖", "desc": "Half rack + 2 sides + soda"},
            "DL6": {"name": "Fish & Chips Combo", "price": 18.49, "emoji": "🐟", "desc": "Fish & chips + soda"},
        }
    },

    "fastfood": {
        "name": "🍔 Burgers & Fast Food",
        "items": {
            "FF1": {"name": "Classic Smash Burger", "price": 12.99, "emoji": "🍔", "desc": "Double patty, special sauce, lettuce"},
            "FF2": {"name": "Crispy Chicken Sandwich", "price": 11.99, "emoji": "🍗", "desc": "Crispy fried chicken, pickles, mayo"},
            "FF3": {"name": "BBQ Bacon Burger", "price": 14.99, "emoji": "🥓", "desc": "Beef patty, bacon, BBQ sauce, onion rings"},
            "FF4": {"name": "Veggie Delight Burger", "price": 10.99, "emoji": "🥬", "desc": "Plant-based patty, avocado, fresh veggies"},
            "FF5": {"name": "Spicy Jalapeño Burger", "price": 13.99, "emoji": "🌶️", "desc": "Beef patty, jalapeños, pepper jack cheese"},
        }
    },

    "pizza": {
        "name": "🍕 Pizza (12”)",
        "items": {
            "PZ1": {"name": "Margherita Classic", "price": 13.99, "emoji": "🍕", "desc": "Fresh mozzarella, tomato, basil"},
            "PZ2": {"name": "BBQ Chicken Pizza", "price": 15.99, "emoji": "🍗", "desc": "Grilled chicken, BBQ sauce, red onions"},
            "PZ3": {"name": "Meat Lovers Supreme", "price": 17.99, "emoji": "🥩", "desc": "Pepperoni, sausage, beef, bacon"},
            "PZ4": {"name": "Veggie Garden Pizza", "price": 14.99, "emoji": "🥦", "desc": "Bell peppers, mushrooms, olives, onions"},
            "PZ5": {"name": "Buffalo Chicken Pizza", "price": 16.99, "emoji": "🔥", "desc": "Buffalo sauce, chicken, ranch drizzle"},
        }
    },

    "bbq": {
        "name": "🍖 BBQ",
        "items": {
            "BB1": {"name": "Half Rack Ribs", "price": 18.99, "emoji": "🍖", "desc": "Smoky ribs, BBQ glaze (choose 2 sides)"},
            "BB2": {"name": "Full Rack Ribs", "price": 29.99, "emoji": "🍖", "desc": "Full rack (choose 2 sides)"},
            "BB3": {"name": "Pulled Pork Sandwich", "price": 12.99, "emoji": "🥪", "desc": "Slow-cooked pork, slaw, BBQ sauce"},
            "BB4": {"name": "Smoked Brisket Plate", "price": 19.99, "emoji": "🥩", "desc": "Sliced brisket (choose 2 sides)"},
            "BB5": {"name": "BBQ Chicken Plate", "price": 16.99, "emoji": "🍗", "desc": "BBQ chicken (choose 2 sides)"},
        }
    },

    "fish": {
        "name": "🐟 Fish & Seafood",
        "items": {
            "FS1": {"name": "Fish & Chips (Cod)", "price": 15.99, "emoji": "🐟", "desc": "Beer-battered cod, fries, tartar"},
            "FS2": {"name": "Blackened Salmon Plate", "price": 19.99, "emoji": "🍣", "desc": "Rice + side salad, lemon butter"},
            "FS3": {"name": "Shrimp Basket", "price": 16.99, "emoji": "🍤", "desc": "Crispy shrimp, fries, cocktail sauce"},
            "FS4": {"name": "Fish Sandwich", "price": 13.49, "emoji": "🥪", "desc": "Fried cod, lettuce, pickles, tartar"},
        }
    },

    "sides": {
        "name": "🍟 Sides & Snacks",
        "items": {
            "SD1": {"name": "Crispy French Fries", "price": 3.99, "emoji": "🍟", "desc": "Golden & crispy, seasoned salt"},
            "SD2": {"name": "Onion Rings", "price": 4.99, "emoji": "⭕", "desc": "Beer battered, crispy"},
            "SD3": {"name": "Mac & Cheese Bites", "price": 5.99, "emoji": "🧀", "desc": "Creamy inside, crispy outside"},
            "SD4": {"name": "Chicken Wings (6pc)", "price": 8.99, "emoji": "🍗", "desc": "Buffalo or BBQ sauce"},
            "SD5": {"name": "Loaded Nachos", "price": 7.99, "emoji": "🌮", "desc": "Cheese, jalapeños, sour cream, salsa"},
            "SD6": {"name": "Caesar Salad", "price": 6.99, "emoji": "🥗", "desc": "Romaine, croutons, parmesan"},
        }
    },

    "drinks": {
        "name": "🥤 Drinks & Shakes",
        "items": {
            "DR1": {"name": "Coca Cola", "price": 2.99, "emoji": "🥤", "desc": "Ice cold, 16oz"},
            "DR2": {"name": "Pepsi", "price": 2.99, "emoji": "🥤", "desc": "Ice cold, 16oz"},
            "DR3": {"name": "Fresh Orange Juice", "price": 4.99, "emoji": "🍊", "desc": "Freshly squeezed, 12oz"},
            "DR4": {"name": "Mango Lassi", "price": 5.99, "emoji": "🥭", "desc": "Fresh mango, yogurt, cardamom"},
            "DR5": {"name": "Strawberry Milkshake", "price": 6.99, "emoji": "🍓", "desc": "Real strawberries, thick & creamy"},
            "DR6": {"name": "Lemonade", "price": 3.99, "emoji": "🍋", "desc": "Fresh squeezed, 16oz"},
            "DR7": {"name": "Iced Coffee", "price": 4.99, "emoji": "☕", "desc": "Cold brew, milk, sugar"},
            "DR8": {"name": "Water (Bottle)", "price": 1.99, "emoji": "💧", "desc": "500ml spring water"},
        }
    },

    "desserts": {
        "name": "🍰 Desserts",
        "items": {
            "DS1": {"name": "Chocolate Lava Cake", "price": 6.99, "emoji": "🍫", "desc": "Warm, gooey center, vanilla ice cream"},
            "DS2": {"name": "NY Cheesecake", "price": 5.99, "emoji": "🍰", "desc": "Classic NY style, strawberry topping"},
            "DS3": {"name": "Oreo Milkshake", "price": 7.99, "emoji": "🥛", "desc": "Thick shake, crushed Oreos, whipped cream"},
            "DS4": {"name": "Brownie Sundae", "price": 6.99, "emoji": "🍨", "desc": "Warm brownie, vanilla ice cream, choc sauce"},
        }
    }
}

# For legacy combo mapping (still used as fallback)
UPSELL_COMBOS = {
    "FF1": ["SD1", "DR1"],
    "FF2": ["SD1", "DR1"],
    "FF3": ["SD2", "DR1"],
    "PZ1": ["SD4", "DR6"],
    "PZ3": ["SD4", "DR1"],
    "FS1": ["DR1"],
}

MENU_SUMMARY = """
Wild Bites Restaurant Menu (US):
🔥 Deals: Burger combo add-on, pizza+wings, family deals
🍔 Burgers: Classic Smash, Crispy Chicken, BBQ Bacon, Veggie, Spicy Jalapeño
🍕 Pizza (12”): Margherita, BBQ Chicken, Meat Lovers, Veggie, Buffalo Chicken
🍖 BBQ: Ribs, Brisket, Pulled Pork, BBQ Chicken
🐟 Fish: Fish & chips, Salmon, Shrimp basket, Fish sandwich
🥤 Drinks: Coke/Pepsi, lemonade, shakes, iced coffee
🍟 Sides: Fries, onion rings, wings, nachos, salad
🍰 Desserts: Lava cake, cheesecake, brownie sundae
Hours: 10am-11pm daily | Delivery: 30-45 mins | Pickup: 15-20 mins | Free delivery over $25
"""

# ----------------------------
# ORDER UTILITIES
# ----------------------------
def get_order_total(order):
    return sum(v["item"]["price"] * v["qty"] for v in order.values())

def get_order_text(order):
    if not order:
        return "Empty cart"
    lines = []
    for item_id, v in order.items():
        item = v["item"]
        qty = v["qty"]
        subtotal = item["price"] * qty
        lines.append(f"{item['emoji']} {item['name']} x{qty} — ${subtotal:.2f}")
    return "\n".join(lines)

def has_any_side(order):
    return any(k.startswith("SD") for k in order.keys())

def has_any_drink(order):
    return any(k.startswith("DR") for k in order.keys())

def is_burger(item_id): return item_id.startswith("FF")
def is_pizza(item_id): return item_id.startswith("PZ")
def is_bbq(item_id): return item_id.startswith("BB")
def is_fish(item_id): return item_id.startswith("FS")

def find_item(item_id):
    for cat_key, cat_data in MENU.items():
        if item_id in cat_data["items"]:
            return cat_key, cat_data["items"][item_id]
    return None, None

def guess_category(text_lower: str):
    t = text_lower
    if any(w in t for w in ["deal", "combo", "offer", "special"]): return "deals"
    if any(w in t for w in ["burger", "smash", "bacon", "jalap", "cheese burger", "cheeseburger", "chicken sandwich"]): return "fastfood"
    if any(w in t for w in ["pizza", "pepperoni", "margherita", "slice", "meat lovers"]): return "pizza"
    if any(w in t for w in ["bbq", "ribs", "brisket", "pulled pork"]): return "bbq"
    if any(w in t for w in ["fish", "salmon", "shrimp", "seafood", "chips"]): return "fish"
    if any(w in t for w in ["drink", "coke", "pepsi", "shake", "lemonade", "iced coffee"]): return "drinks"
    if any(w in t for w in ["dessert", "cake", "cheesecake", "brownie", "sweet"]): return "desserts"
    if any(w in t for w in ["side", "fries", "wings", "nachos", "rings"]): return "sides"
    return None

# ----------------------------
# WEBHOOK
# ----------------------------
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Forbidden", status_code=403)

@app.post("/webhook")
async def handle_webhook(request: Request):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            sender = message["from"]
            msg_type = message.get("type", "")

            if msg_type == "text":
                text = message["text"]["body"].strip()
                print(f"MSG: {text} from {sender}")
                await handle_flow(sender, text)

            elif msg_type == "interactive":
                interactive = message["interactive"]
                if interactive["type"] == "button_reply":
                    btn_id = interactive["button_reply"]["id"]
                    print(f"BTN: {btn_id} from {sender}")
                    await handle_flow(sender, btn_id, 
...(truncated)...