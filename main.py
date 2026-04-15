import os
import aiohttp
import traceback
import random
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import uvicorn

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"Token: {WHATSAPP_TOKEN[:20] if WHATSAPP_TOKEN else 'MISSING'}...")
print(f"Phone ID: {WHATSAPP_PHONE_NUMBER_ID}")

customer_sessions = {}

MENU = {
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
        "name": "🍕 Pizza",
        "items": {
            "PZ1": {"name": "Margherita Classic", "price": 13.99, "emoji": "🍕", "desc": "Fresh mozzarella, tomato, basil"},
            "PZ2": {"name": "BBQ Chicken Pizza", "price": 15.99, "emoji": "🍗", "desc": "Grilled chicken, BBQ sauce, red onions"},
            "PZ3": {"name": "Meat Lovers Supreme", "price": 17.99, "emoji": "🥩", "desc": "Pepperoni, sausage, beef, bacon"},
            "PZ4": {"name": "Veggie Garden Pizza", "price": 14.99, "emoji": "🥦", "desc": "Bell peppers, mushrooms, olives, onions"},
            "PZ5": {"name": "Buffalo Chicken Pizza", "price": 16.99, "emoji": "🔥", "desc": "Buffalo sauce, chicken, ranch drizzle"},
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

UPSELL_COMBOS = {
    "FF1": ["SD1", "DR1"],
    "FF2": ["SD1", "DR3"],
    "FF3": ["SD2", "DR1"],
    "PZ1": ["SD6", "DR6"],
    "PZ3": ["SD4", "DR1"],
}

MENU_SUMMARY = """
Wild Bites Restaurant Menu:
🍔 Burgers: Classic Smash ($12.99), Crispy Chicken ($11.99), BBQ Bacon ($14.99), Veggie ($10.99), Spicy Jalapeño ($13.99)
🍕 Pizza: Margherita ($13.99), BBQ Chicken ($15.99), Meat Lovers ($17.99), Veggie ($14.99), Buffalo ($16.99)
🥤 Drinks: Coke/Pepsi ($2.99), OJ ($4.99), Mango Lassi ($5.99), Milkshake ($6.99), Lemonade ($3.99), Iced Coffee ($4.99)
🍟 Sides: Fries ($3.99), Onion Rings ($4.99), Mac Bites ($5.99), Wings ($8.99), Nachos ($7.99), Salad ($6.99)
🍰 Desserts: Lava Cake ($6.99), Cheesecake ($5.99), Oreo Shake ($7.99), Brownie Sundae ($6.99)
Hours: 10am-11pm daily | Delivery: 30-45 mins | Pickup: 15-20 mins | Free delivery over $25
"""

def get_session(sender):
    if sender not in customer_sessions:
        customer_sessions[sender] = {
            "stage": "ai_chat",
            "order": {},
            "delivery_type": "",
            "address": "",
            "name": "",
            "payment": "",
            "last_added": None,
            "conversation": []
        }
    return customer_sessions[sender]

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

# ── WEBHOOK ───────────────────────────────────────────────────────────

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
                    await handle_flow(sender, btn_id, is_button=True)
                elif interactive["type"] == "list_reply":
                    list_id = interactive["list_reply"]["id"]
                    print(f"LIST: {list_id} from {sender}")
                    await handle_flow(sender, list_id, is_button=True)
    except Exception as e:
        print(f"ERROR: {e}\n{traceback.format_exc()}")
    return {"status": "ok"}

# ── FLOW HANDLER ──────────────────────────────────────────────────────

async def handle_flow(sender, text, is_button=False):
    session = get_session(sender)
    stage = session["stage"]
    text_lower = text.lower().strip()

    # ── RESET ────────────────────────────────────────────────────────
    if text_lower in ["restart", "reset", "start over"]:
        customer_sessions[sender] = {"stage": "ai_chat", "order": {}, "delivery_type": "", "address": "", "name": "", "payment": "", "last_added": None, "conversation": []}
        await send_text_message(sender, "👋 Hey! I'm Alex from Wild Bites. How can I help you today? 😊")
        return

    # ── CATEGORY BUTTONS — Always works regardless of stage ──────────
    cat_map = {
        "CAT_FASTFOOD": "fastfood",
        "CAT_PIZZA": "pizza",
        "CAT_DRINKS": "drinks",
        "CAT_SIDES": "sides",
        "CAT_DESSERTS": "desserts"
    }
    if text in cat_map:
        cat_key = cat_map[text]
        session["stage"] = "items"
        session["current_cat"] = cat_key
        await send_category_items(sender, cat_key, session["order"])
        return

    # ── ITEM ADD — Always works ──────────────────────────────────────
    if text.startswith("ADD_"):
        item_id = text.replace("ADD_", "")
        found_item = None
        for cat_key, cat_data in MENU.items():
            if item_id in cat_data["items"]:
                found_item = cat_data["items"][item_id]
                break
        if found_item:
            if item_id in session["order"]:
                session["order"][item_id]["qty"] += 1
            else:
                session["order"][item_id] = {"item": found_item, "qty": 1}
            session["last_added"] = item_id
            session["stage"] = "qty_control"
            if item_id in UPSELL_COMBOS and len(session["order"]) == 1:
                await send_upsell(sender, item_id, found_item, session["order"])
            else:
                await send_qty_control(sender, item_id, found_item, session["order"])
        return

    # ── QTY CONTROL — Always works ───────────────────────────────────
    if text in ["QTY_PLUS", "QTY_MINUS"]:
        item_id = session.get("last_added")
        if text == "QTY_PLUS" and item_id and item_id in session["order"]:
            session["order"][item_id]["qty"] += 1
            await send_qty_control(sender, item_id, session["order"][item_id]["item"], session["order"])
        elif text == "QTY_MINUS" and item_id:
            if item_id in session["order"]:
                if session["order"][item_id]["qty"] > 1:
                    session["order"][item_id]["qty"] -= 1
                else:
                    del session["order"][item_id]
            if session["order"] and item_id in session["order"]:
                await send_qty_control(sender, item_id, session["order"][item_id]["item"], session["order"])
            else:
                session["stage"] = "menu"
                await send_main_menu(sender, session["order"])
        return

    # ── CHECKOUT — Always works ──────────────────────────────────────
    if text == "CHECKOUT":
        if session["order"]:
            session["stage"] = "upsell_check"
            await send_dessert_upsell(sender, session["order"])
        else:
            await send_text_message(sender, "🛒 Your cart is empty! Add some items first 😊")
            await send_main_menu(sender)
        return

    # ── UNIVERSAL BUTTONS ────────────────────────────────────────────
    if text == "VIEW_CART":
        await send_cart_view(sender, session["order"])
        return

    if text in ["ADD_MORE", "BACK_MENU", "SHOW_MENU"]:
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"])
        return

    # ── UPSELL COMBO ─────────────────────────────────────────────────
    if text in ["YES_COMBO", "NO_COMBO"]:
        if text == "YES_COMBO":
            for cid in session.get("pending_combo", []):
                for cat_key, cat_data in MENU.items():
                    if cid in cat_data["items"] and cid not in session["order"]:
                        session["order"][cid] = {"item": cat_data["items"][cid], "qty": 1}
        session["stage"] = "qty_control"
        last = session.get("last_added")
        if last and last in session["order"]:
            await send_qty_control(sender, last, session["order"][last]["item"], session["order"])
        else:
            await send_main_menu(sender, session["order"])
        return

    # ── DESSERT UPSELL ───────────────────────────────────────────────
    if text in ["YES_UPSELL", "NO_UPSELL"]:
        if text == "YES_UPSELL":
            session["stage"] = "items"
            session["current_cat"] = "desserts"
            await send_category_items(sender, "desserts", session["order"])
        else:
            session["stage"] = "confirm"
            await send_order_summary(sender, session["order"])
        return

    # ── ORDER CONFIRM/CANCEL ─────────────────────────────────────────
    if text == "CONFIRM_ORDER":
        session["stage"] = "get_name"
        await send_text_message(sender, "👤 *What's your name?*\n\nJust your first name is fine! 😊")
        return

    if text == "CANCEL_ORDER":
        customer_sessions[sender] = {"stage": "ai_chat", "order": {}, "delivery_type": "", "address": "", "name": "", "payment": "", "last_added": None, "conversation": []}
        await send_text_message(sender, "❌ Order cancelled! No worries 😊\n\nType *menu* to start again!")
        return

    # ── DELIVERY ─────────────────────────────────────────────────────
    if text in ["DELIVERY", "PICKUP"]:
        if text == "DELIVERY":
            session["delivery_type"] = "delivery"
            session["stage"] = "address"
            name = session.get("name", "")
            await send_text_message(sender, f"📍 *Hey {name}! What's your delivery address?*\n\nPlease type your full address:\n\nExample: 123 Main St, Apt 4B, New York, NY 10001")
        else:
            session["delivery_type"] = "pickup"
            session["stage"] = "payment"
            await send_payment_buttons(sender, session.get("name", ""))
        return

    # ── PAYMENT ──────────────────────────────────────────────────────
    if text in ["CASH", "CARD", "APPLE_PAY"]:
        payment_map = {
            "CASH": "💵 Cash on Delivery",
            "CARD": "💳 Credit/Debit Card",
            "APPLE_PAY": "📱 Apple/Google Pay"
        }
        session["payment"] = payment_map[text]
        await send_order_confirmed(sender, session)
        customer_sessions[sender] = {"stage": "ai_chat", "order": {}, "delivery_type": "", "address": "", "name": "", "payment": "", "last_added": None, "conversation": []}
        return

    # ── STAGE-SPECIFIC TEXT ──────────────────────────────────────────
    if stage == "get_name":
        session["name"] = text.title()
        session["stage"] = "delivery"
        await send_delivery_buttons(sender, text.title())
        return

    if stage == "address":
        session["address"] = text
        session["stage"] = "payment"
        await send_text_message(sender, f"✅ *Got it!*\n📍 {text}\n\nNow let's sort out payment 👇")
        await send_payment_buttons(sender, session.get("name", ""))
        return

    # ── GREETINGS + ORDER INTENT ─────────────────────────────────────
    if text_lower in ["hi", "hello", "hey", "menu", "order", "start", "salam", "hola"]:
        session["stage"] = "menu"
        greeting = await get_ai_response(sender, text, "User said hi or wants to order. Give a warm friendly 1-line greeting only.")
        await send_text_message(sender, greeting)
        await send_main_menu(sender)
        return

    # ── AI HANDLES EVERYTHING ELSE ───────────────────────────────────
    reply = await get_ai_response(sender, text)
    await send_text_message(sender, reply)
    session["conversation"].append(text)
    if len(session["conversation"]) >= 2:
        await send_menu_suggestion(sender)
        session["conversation"] = []

# ── AI RESPONSE ───────────────────────────────────────────────────────

async def get_ai_response(sender, user_message, extra_instruction=""):
    system_prompt = f"""You are Alex, a friendly customer service rep at Wild Bites Restaurant in the US.

Your personality:
- Warm, friendly, helpful — like a real human staff member
- Casual but professional
- Use emojis naturally (not too many)
- Short responses — max 3-4 sentences
- If someone asks about food, recommend something specific
- If someone complains, apologize sincerely and offer to help
- If someone asks about hours: "We're open 10am-11pm daily"
- If someone asks about location: "We deliver citywide and have a pickup location downtown"
- NEVER say you're an AI or bot
- Reply in the same language the user writes in

{MENU_SUMMARY}

{extra_instruction}"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.8,
        "max_tokens": 150
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers
            ) as r:
                result = await r.json()
                return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"AI Error: {e}")
        return "Hey! Sorry about that, had a small hiccup. How can I help you? 😊"

# ── SEND FUNCTIONS ────────────────────────────────────────────────────

async def send_menu_suggestion(sender):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "By the way, are you hungry? 🍔 Check out our menu!"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "SHOW_MENU", "title": "🍽️ Show Me the Menu!"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Menu suggestion sent")

async def send_main_menu(sender, current_order={}):
    total = get_order_total(current_order)
    cart_text = ""
    if current_order:
        count = sum(v["qty"] for v in current_order.values())
        cart_text = f"\n\n🛒 *Cart: {count} item(s) — ${total:.2f}*"

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "🍽️ Wild Bites Restaurant"},
            "body": {"text": f"What are you craving today? 😋{cart_text}\n\nTap a category below 👇"},
            "footer": {"text": "🚀 Fast Delivery | Fresh Food | Best Price"},
            "action": {
                "button": "📋 Browse Menu",
                "sections": [
                    {
                        "title": "🍔 Main Course",
                        "rows": [
                            {"id": "CAT_FASTFOOD", "title": "🍔 Burgers & Fast Food", "description": "Smash Burgers, Chicken — from $10.99"},
                            {"id": "CAT_PIZZA", "title": "🍕 Pizza", "description": "Classic & Specialty — from $13.99"},
                        ]
                    },
                    {
                        "title": "🥤 Extras",
                        "rows": [
                            {"id": "CAT_SIDES", "title": "🍟 Sides & Snacks", "description": "Fries, Wings, Nachos — from $3.99"},
                            {"id": "CAT_DRINKS", "title": "🥤 Drinks & Shakes", "description": "Soft Drinks, Juices, Shakes — from $1.99"},
                            {"id": "CAT_DESSERTS", "title": "🍰 Desserts", "description": "Cakes, Shakes, Brownies — from $5.99"},
                        ]
                    }
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Main menu sent")

async def send_category_items(sender, cat_key, current_order):
    cat = MENU[cat_key]
    total = get_order_total(current_order)
    cart_text = f"\n\n🛒 Cart Total: ${total:.2f}" if current_order else ""
    rows = []
    for item_id, item in cat["items"].items():
        in_cart = current_order.get(item_id, {}).get("qty", 0)
        cart_indicator = f" ✅x{in_cart}" if in_cart else ""
        rows.append({
            "id": f"ADD_{item_id}",
            "title": f"{item['emoji']} {item['name']}{cart_indicator}",
            "description": f"${item['price']:.2f} • {item['desc']}"
        })

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": cat["name"]},
            "body": {"text": f"Tap any item to add to your cart! 👇{cart_text}"},
            "footer": {"text": "✅ in cart indicator shows what you've added"},
            "action": {
                "button": "Select Item",
                "sections": [{"title": cat["name"], "rows": rows}]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Category sent: {cat_key}")

async def send_qty_control(sender, item_id, item, order):
    qty = order.get(item_id, {}).get("qty", 1)
    subtotal = item["price"] * qty
    total = get_order_total(order)
    order_text = get_order_text(order)

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": f"✅ {item['emoji']} Added to Cart!"},
            "body": {
                "text": f"*{item['name']}*\nQty: {qty} × ${item['price']:.2f} = *${subtotal:.2f}*\n\n{'─'*20}\n📋 *Your Order:*\n{order_text}\n{'─'*20}\n💰 *Total: ${total:.2f}*"
            },
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "QTY_MINUS", "title": "➖ Remove One"}},
                    {"type": "reply", "reply": {"id": "QTY_PLUS", "title": "➕ Add One More"}},
                    {"type": "reply", "reply": {"id": "ADD_MORE", "title": "🍽️ Add More Items"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Qty control sent")

    await send_checkout_prompt(sender, total)

async def send_checkout_prompt(sender, total):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "Ready to place your order? 🚀"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "CHECKOUT", "title": f"✅ Checkout ${total:.2f}"}},
                    {"type": "reply", "reply": {"id": "VIEW_CART", "title": "🛒 View Cart"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Checkout prompt sent")

async def send_upsell(sender, item_id, item, order):
    combo = UPSELL_COMBOS.get(item_id, [])
    combo_names = []
    combo_total = 0
    for cid in combo:
        for cat_key, cat_data in MENU.items():
            if cid in cat_data["items"]:
                citem = cat_data["items"][cid]
                combo_names.append(f"{citem['emoji']} {citem['name']}")
                combo_total += citem["price"]

    session = get_session(sender)
    session["stage"] = "upsell_combo"
    session["pending_combo"] = combo
    combo_text = " + ".join(combo_names)

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "🔥 Make it a Combo?"},
            "body": {
                "text": f"Complete your meal with:\n\n{combo_text}\n\nFor only *${combo_total:.2f} more!* 🎉\n\nMost customers love this combo! 😍"
            },
            "footer": {"text": "Best value deal!"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "YES_COMBO", "title": "✅ Yes! Add Combo"}},
                    {"type": "reply", "reply": {"id": "NO_COMBO", "title": "❌ No Thanks"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Upsell sent")

async def send_dessert_upsell(sender, order):
    total = get_order_total(order)
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "🍰 Save Room for Dessert?"},
            "body": {
                "text": f"Your order is ${total:.2f}.\n\nTreat yourself! 😍\n\n🍫 Chocolate Lava Cake — $6.99\n🍰 NY Cheesecake — $5.99\n🍨 Brownie Sundae — $6.99\n🥛 Oreo Milkshake — $7.99"
            },
            "footer": {"text": "Life is short, eat dessert! 🍰"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "YES_UPSELL", "title": "🍰 Yes, Add Dessert!"}},
                    {"type": "reply", "reply": {"id": "NO_UPSELL", "title": "✅ No, Checkout Now"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Dessert upsell sent")

async def send_cart_view(sender, order):
    if not order:
        await send_text_message(sender, "🛒 Your cart is empty!\n\nType *menu* to browse our delicious options! 😊")
        return
    total = get_order_total(order)
    order_text = get_order_text(order)
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "🛒 Your Cart"},
            "body": {"text": f"{order_text}\n\n{'─'*25}\n💰 *Subtotal: ${total:.2f}*\n🚚 Delivery fee calculated at checkout"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "CHECKOUT", "title": f"✅ Checkout ${total:.2f}"}},
                    {"type": "reply", "reply": {"id": "ADD_MORE", "title": "➕ Add More Items"}},
                    {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": "❌ Clear Cart"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Cart view sent")

async def send_order_summary(sender, order):
    total = get_order_total(order)
    tax = total * 0.08
    grand_total = total + tax
    order_text = get_order_text(order)
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "📋 Order Summary"},
            "body": {
                "text": f"{order_text}\n\n{'─'*25}\n💰 Subtotal: ${total:.2f}\n📊 Tax (8%): ${tax:.2f}\n{'─'*25}\n💵 *Total: ${grand_total:.2f}*\n\nReady to confirm? ✅"
            },
            "footer": {"text": "Wild Bites — Fresh & Fast!"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "CONFIRM_ORDER", "title": "✅ Confirm Order"}},
                    {"type": "reply", "reply": {"id": "ADD_MORE", "title": "➕ Add More"}},
                    {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": "❌ Cancel"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Order summary sent")

async def send_delivery_buttons(sender, name):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": f"🚚 Hey {name}! How do you want your order?"},
            "body": {
                "text": "🚚 *Home Delivery* — 30-45 mins\n   Free delivery on orders over $25!\n\n🏪 *Store Pickup* — Ready in 15-20 mins\n   Skip the wait!"
            },
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "DELIVERY", "title": "🚚 Home Delivery"}},
                    {"type": "reply", "reply": {"id": "PICKUP", "title": "🏪 Store Pickup"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Delivery buttons sent")

async def send_payment_buttons(sender, name):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "💳 How would you like to pay?"},
            "body": {"text": "Choose your payment method:\n\n💵 *Cash* — Pay at door/pickup\n💳 *Card* — Visa, MC, Amex\n📱 *Apple/Google Pay* — Tap & pay"},
            "footer": {"text": "100% Secure Payment 🔒"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "CASH", "title": "💵 Cash"}},
                    {"type": "reply", "reply": {"id": "CARD", "title": "💳 Card"}},
                    {"type": "reply", "reply": {"id": "APPLE_PAY", "title": "📱 Apple/Google Pay"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print("Payment buttons sent")

async def send_order_confirmed(sender, session_data):
    order = session_data.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    grand_total = total + tax
    order_text = get_order_text(order)
    delivery_type = session_data.get("delivery_type", "pickup")
    address = session_data.get("address", "")
    payment = session_data.get("payment", "Cash")
    name = session_data.get("name", "Customer")
    order_id = random.randint(10000, 99999)
    eta = "30-45 minutes" if delivery_type == "delivery" else "15-20 minutes"

    msg = f"""🎉 *Order Confirmed, {name}!*

📋 *Order #{order_id}*

{order_text}

{'─'*25}
💰 Subtotal: ${total:.2f}
📊 Tax (8%): ${tax:.2f}
{'─'*25}
💵 *Total: ${grand_total:.2f}*

{'🚚 Delivery to: ' + address if delivery_type == 'delivery' else '🏪 Store Pickup'}
💳 Payment: {payment}
⏱️ Ready in: *{eta}*

We'll keep you posted! 📱❤️

Thank you for choosing Wild Bites! 🍔
Type *Hi* to order again anytime!"""

    await send_text_message(sender, msg)

async def send_text_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Text sent to {to}")

@app.post("/twilio-call")
async def twilio_call(request: Request):
    from fastapi.responses import HTMLResponse
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Welcome to Wild Bites Restaurant. Please send us a WhatsApp message to place your order. Thank you!</Say>
</Response>"""
    return HTMLResponse(content=twiml, media_type="application/xml")

@app.post("/twilio-sms")
async def twilio_sms(request: Request):
    form = await request.form()
    print(f"SMS: {form.get('Body')} from {form.get('From')}")
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")