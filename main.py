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

print(f"Token: {WHATSAPP_TOKEN[:20] if WHATSAPP_TOKEN else 'MISSING'}...")
print(f"Phone ID: {WHATSAPP_PHONE_NUMBER_ID}")

customer_sessions = {}

MENU = {
    "Burgers": {
        "1": {"name": "Classic Burger", "price": 25, "emoji": "🍔"},
        "2": {"name": "Zinger Burger", "price": 30, "emoji": "🔥"},
        "3": {"name": "BBQ Burger", "price": 35, "emoji": "🤤"},
    },
    "Pizza": {
        "4": {"name": "Margherita", "price": 40, "emoji": "🍕"},
        "5": {"name": "BBQ Chicken", "price": 50, "emoji": "🍗"},
        "6": {"name": "Pepperoni", "price": 55, "emoji": "🌶️"},
    },
    "Drinks": {
        "7": {"name": "Coca Cola", "price": 10, "emoji": "🥤"},
        "8": {"name": "Fresh Juice", "price": 15, "emoji": "🍹"},
        "9": {"name": "Water", "price": 5, "emoji": "💧"},
    },
    "Sides": {
        "10": {"name": "French Fries", "price": 15, "emoji": "🍟"},
        "11": {"name": "Onion Rings", "price": 18, "emoji": "⭕"},
        "12": {"name": "Coleslaw", "price": 12, "emoji": "🥗"},
    }
}

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
                text = message["text"]["body"].strip().lower()
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

async def handle_flow(sender, text, is_button=False):
    if sender not in customer_sessions:
        customer_sessions[sender] = {"stage": "welcome", "order": [], "delivery_type": "", "address": "", "payment": ""}
    
    session = customer_sessions[sender]
    stage = session["stage"]

    # Reset triggers
    if text in ["hi", "hello", "salam", "start", "menu", "order", "hey", "salaam", "مرحبا", "hola"]:
        customer_sessions[sender] = {"stage": "menu", "order": [], "delivery_type": "", "address": "", "payment": ""}
        await send_main_menu(sender)
        return

    if stage == "welcome":
        customer_sessions[sender]["stage"] = "menu"
        await send_main_menu(sender)
        return

    if stage == "menu":
        cat_map = {
            "CAT_BURGERS": "Burgers",
            "CAT_PIZZA": "Pizza", 
            "CAT_DRINKS": "Drinks",
            "CAT_SIDES": "Sides"
        }
        if text in cat_map:
            cat = cat_map[text]
            session["stage"] = "items"
            session["current_cat"] = cat
            await send_category_buttons(sender, cat)
        else:
            await send_main_menu(sender)
        return

    if stage == "items":
        item_id = text.replace("ITEM_", "")
        found = None
        for cat, items in MENU.items():
            if item_id in items:
                found = {**items[item_id], "id": item_id}
                break
        if found:
            session["order"].append(found)
            session["stage"] = "add_more"
            await send_item_added(sender, found, session["order"])
        else:
            await send_category_buttons(sender, session.get("current_cat", "Burgers"))
        return

    if stage == "add_more":
        if text == "ADD_MORE":
            session["stage"] = "menu"
            await send_main_menu(sender, session["order"])
        elif text == "CHECKOUT":
            session["stage"] = "confirm"
            await send_order_summary(sender, session["order"])
        elif text == "REMOVE_LAST":
            if session["order"]:
                removed = session["order"].pop()
                await send_text_message(sender, f"❌ *{removed['name']}* remove ho gaya!")
            if session["order"]:
                await send_add_more_buttons(sender, session["order"])
            else:
                session["stage"] = "menu"
                await send_main_menu(sender)
        else:
            await send_add_more_buttons(sender, session["order"])
        return

    if stage == "confirm":
        if text == "CONFIRM_ORDER":
            session["stage"] = "delivery"
            await send_delivery_buttons(sender)
        elif text == "ADD_MORE":
            session["stage"] = "menu"
            await send_main_menu(sender, session["order"])
        elif text == "CANCEL_ORDER":
            customer_sessions[sender] = {"stage": "menu", "order": [], "delivery_type": "", "address": "", "payment": ""}
            await send_text_message(sender, "❌ Order cancel!\n\nDobara order ke liye *Hi* likhein! 😊")
        else:
            await send_order_summary(sender, session["order"])
        return

    if stage == "delivery":
        if text == "DELIVERY":
            session["delivery_type"] = "delivery"
            session["stage"] = "address"
            await send_text_message(sender, "🏠 *Apna delivery address likhein:*\n\nMisaal: Villa 5, Al Barsha, Dubai")
        elif text == "PICKUP":
            session["delivery_type"] = "pickup"
            session["stage"] = "payment"
            await send_payment_buttons(sender)
        else:
            await send_delivery_buttons(sender)
        return

    if stage == "address":
        session["address"] = text
        session["stage"] = "payment"
        await send_text_message(sender, f"✅ Address save!\n📍 *{text}*")
        await send_payment_buttons(sender)
        return

    if stage == "payment":
        if text in ["CASH", "CARD"]:
            session["payment"] = "Cash on Delivery 💵" if text == "CASH" else "Card/Online 💳"
            await send_order_confirmed(sender, session)
            customer_sessions[sender] = {"stage": "welcome", "order": [], "delivery_type": "", "address": "", "payment": ""}
        else:
            await send_payment_buttons(sender)
        return

    await send_main_menu(sender)

# ── MAIN MENU — List with buttons ────────────────────────────────────
async def send_main_menu(sender, current_order=[]):
    cart_text = ""
    if current_order:
        total = sum(i["price"] for i in current_order)
        items_text = " | ".join([f"{i['emoji']} {i['name']}" for i in current_order])
        cart_text = f"\n\n🛒 *Cart:* {items_text}\n💰 *Total: AED {total}*"

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "🍽️ Wild Restaurant"},
            "body": {"text": f"Assalam o Alaikum! Kya khana chahenge aaj? 😊{cart_text}\n\nNeechay se category chunein 👇"},
            "footer": {"text": "24/7 Available | Fast Delivery"},
            "action": {
                "button": "🍽️ Menu Dekhein",
                "sections": [
                    {
                        "title": "🍔 Fast Food",
                        "rows": [
                            {"id": "CAT_BURGERS", "title": "🍔 Burgers", "description": "Classic, Zinger, BBQ — AED 25-35"},
                            {"id": "CAT_PIZZA", "title": "🍕 Pizza", "description": "Margherita, BBQ, Pepperoni — AED 40-55"},
                        ]
                    },
                    {
                        "title": "🥤 Extras",
                        "rows": [
                            {"id": "CAT_DRINKS", "title": "🥤 Drinks", "description": "Cola, Juice, Water — AED 5-15"},
                            {"id": "CAT_SIDES", "title": "🍟 Sides", "description": "Fries, Rings, Coleslaw — AED 12-18"},
                        ]
                    }
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            result = await r.json()
            print(f"Main menu: {result.get('messages', 'err')}")

# ── CATEGORY BUTTONS ─────────────────────────────────────────────────
async def send_category_buttons(sender, category):
    items = MENU[category]
    rows = []
    for k, v in items.items():
        rows.append({
            "id": f"ITEM_{k}",
            "title": f"{v['emoji']} {v['name']}",
            "description": f"AED {v['price']}"
        })

    cat_emojis = {"Burgers": "🍔", "Pizza": "🍕", "Drinks": "🥤", "Sides": "🍟"}
    emoji = cat_emojis.get(category, "🍽️")

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": f"{emoji} {category}"},
            "body": {"text": f"*{category}* mein se kya pasand karengy? 😋\n\nNeechay tap karein 👇"},
            "footer": {"text": "Sab fresh bana kar diya jata hai!"},
            "action": {
                "button": f"{emoji} {category} Select Karein",
                "sections": [{"title": category, "rows": rows}]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Category sent: {category}")

# ── ITEM ADDED BUTTONS ───────────────────────────────────────────────
async def send_item_added(sender, item, order):
    total = sum(i["price"] for i in order)
    order_text = "\n".join([f"{i['emoji']} {i['name']} — AED {i['price']}" for i in order])

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": f"✅ {item['emoji']} {item['name']} Add Ho Gaya!"},
            "body": {
                "text": f"🛒 *Aapka Cart:*\n\n{order_text}\n\n{'─'*20}\n💰 *Total: AED {total}*\n\nAur kuch add karna hai? 😊"
            },
            "footer": {"text": "Wild Restaurant"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "ADD_MORE", "title": "➕ Aur Add Karein"}},
                    {"type": "reply", "reply": {"id": "CHECKOUT", "title": "✅ Order Confirm"}},
                    {"type": "reply", "reply": {"id": "REMOVE_LAST", "title": "❌ Last Item Hatao"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Item added sent")

# ── ADD MORE BUTTONS ─────────────────────────────────────────────────
async def send_add_more_buttons(sender, order):
    total = sum(i["price"] for i in order)
    order_text = "\n".join([f"{i['emoji']} {i['name']} — AED {i['price']}" for i in order])

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": f"🛒 *Cart:*\n\n{order_text}\n\n💰 *Total: AED {total}*"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "ADD_MORE", "title": "➕ Aur Add Karein"}},
                    {"type": "reply", "reply": {"id": "CHECKOUT", "title": "✅ Checkout"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Add more sent")

# ── ORDER SUMMARY BUTTONS ────────────────────────────────────────────
async def send_order_summary(sender, order):
    total = sum(i["price"] for i in order)
    order_text = "\n".join([f"{i['emoji']} {i['name']} — AED {i['price']}" for i in order])

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
                "text": f"*Aapka Order:*\n\n{order_text}\n\n{'─'*20}\n💰 *Total: AED {total}*\n\nKya confirm karna hai? ✅"
            },
            "footer": {"text": "Wild Restaurant — Fresh & Fast!"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "CONFIRM_ORDER", "title": "✅ Haan, Confirm!"}},
                    {"type": "reply", "reply": {"id": "ADD_MORE", "title": "➕ Aur Add Karein"}},
                    {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": "❌ Cancel"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Order summary sent")

# ── DELIVERY BUTTONS ─────────────────────────────────────────────────
async def send_delivery_buttons(sender):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "🚚 Delivery ya Pickup?"},
            "body": {"text": "Kaise lena chahenge apna order? 🤔\n\n🚚 *Home Delivery* — 30-45 min\n🏪 *Khud Pickup* — 15-20 min"},
            "footer": {"text": "Wild Restaurant"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "DELIVERY", "title": "🚚 Home Delivery"}},
                    {"type": "reply", "reply": {"id": "PICKUP", "title": "🏪 Khud Pickup"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Delivery options sent")

# ── PAYMENT BUTTONS ──────────────────────────────────────────────────
async def send_payment_buttons(sender):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "💳 Payment Method"},
            "body": {"text": "Kaise payment karenge? 💰"},
            "footer": {"text": "Secure Payment"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "CASH", "title": "💵 Cash on Delivery"}},
                    {"type": "reply", "reply": {"id": "CARD", "title": "💳 Card/Online"}},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Payment options sent")

# ── ORDER CONFIRMED ──────────────────────────────────────────────────
async def send_order_confirmed(sender, session_data):
    order = session_data.get("order", [])
    total = sum(i["price"] for i in order)
    order_text = "\n".join([f"{i['emoji']} {i['name']} — AED {i['price']}" for i in order])
    delivery_type = session_data.get("delivery_type", "pickup")
    address = session_data.get("address", "")
    payment = session_data.get("payment", "Cash")
    order_id = random.randint(1000, 9999)
    eta = "30-45 dakeeqay" if delivery_type == "delivery" else "15-20 dakeeqay"

    msg = f"""🎉 *Order Confirm Ho Gaya!*

📋 *Order #{order_id}*

{order_text}

{'─'*20}
💰 *Total: AED {total}*
{'🚚 Delivery: ' + address if delivery_type == 'delivery' else '🏪 Pickup: Restaurant se'}
💳 *Payment:* {payment}
⏱️ *ETA:* {eta}

Shukriya! Jaldi aa raha hai! 🍽️❤️

Dobara order ke liye *Hi* likhein! 😊"""

    await send_text_message(sender, msg)

# ── TEXT MESSAGE ─────────────────────────────────────────────────────
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
    <Say voice="alice">Welcome to Wild Restaurant. Please send us a WhatsApp message to place your order. Thank you!</Say>
</Response>"""
    return HTMLResponse(content=twiml, media_type="application/xml")

@app.post("/twilio-sms")
async def twilio_sms(request: Request):
    form = await request.form()
    print(f"SMS: {form.get('Body')} from {form.get('From')}")
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")