import os
import aiohttp
import traceback
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

# Customer sessions: { "phone": { "stage": "...", "order": [], "delivery_type": "", "address": "", "payment": "" } }
customer_sessions = {}

MENU = {
    "Burgers": {
        "1": {"name": "Classic Burger", "price": 25},
        "2": {"name": "Zinger Burger", "price": 30},
        "3": {"name": "BBQ Burger", "price": 35},
    },
    "Pizza": {
        "4": {"name": "Margherita Pizza", "price": 40},
        "5": {"name": "BBQ Chicken Pizza", "price": 50},
        "6": {"name": "Pepperoni Pizza", "price": 55},
    },
    "Drinks": {
        "7": {"name": "Coca Cola", "price": 10},
        "8": {"name": "Fresh Juice", "price": 15},
        "9": {"name": "Water", "price": 5},
    },
    "Sides": {
        "10": {"name": "French Fries", "price": 15},
        "11": {"name": "Onion Rings", "price": 18},
        "12": {"name": "Coleslaw", "price": 12},
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
                text = message["text"]["body"].strip()
                print(f"MSG from {sender}: {text}")
                await handle_order_flow(sender, text)
            elif msg_type == "interactive":
                interactive = message["interactive"]
                if interactive["type"] == "button_reply":
                    reply_id = interactive["button_reply"]["id"]
                    await handle_order_flow(sender, reply_id, is_button=True)
                elif interactive["type"] == "list_reply":
                    reply_id = interactive["list_reply"]["id"]
                    await handle_order_flow(sender, reply_id, is_button=True)
    except Exception as e:
        print(f"ERROR: {e}\n{traceback.format_exc()}")
    return {"status": "ok"}

async def handle_order_flow(sender: str, text: str, is_button: bool = False):
    if sender not in customer_sessions:
        customer_sessions[sender] = {"stage": "welcome", "order": [], "delivery_type": "", "address": "", "payment": ""}
    session = customer_sessions[sender]
    stage = session["stage"]
    text_lower = text.lower()

    # Reset on greeting
    if text_lower in ["hi", "hello", "salam", "start", "menu", "order", "hey", "salaam"]:
        customer_sessions[sender] = {"stage": "menu", "order": [], "delivery_type": "", "address": "", "payment": ""}
        await send_main_menu(sender)
        return

    if stage in ["welcome"]:
        customer_sessions[sender]["stage"] = "menu"
        await send_main_menu(sender)
        return

    if stage == "menu":
        if text in ["CAT_BURGERS"]: await send_category_menu(sender, "Burgers"); session["stage"] = "items"; session["current_cat"] = "Burgers"
        elif text in ["CAT_PIZZA"]: await send_category_menu(sender, "Pizza"); session["stage"] = "items"; session["current_cat"] = "Pizza"
        elif text in ["CAT_DRINKS"]: await send_category_menu(sender, "Drinks"); session["stage"] = "items"; session["current_cat"] = "Drinks"
        elif text in ["CAT_SIDES"]: await send_category_menu(sender, "Sides"); session["stage"] = "items"; session["current_cat"] = "Sides"
        else: await send_main_menu(sender)
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
            await send_category_menu(sender, session.get("current_cat", "Burgers"))
        return

    if stage == "add_more":
        if text == "ADD_MORE": session["stage"] = "menu"; await send_main_menu(sender, session["order"])
        elif text == "CHECKOUT": session["stage"] = "confirm"; await send_order_summary(sender, session["order"])
        elif text == "REMOVE_LAST":
            if session["order"]:
                removed = session["order"].pop()
                await send_text_message(sender, f"Removed: {removed['name']}")
            await send_item_added(sender, {}, session["order"]) if session["order"] else await send_main_menu(sender)
        else: await send_add_more_btns(sender, session["order"])
        return

    if stage == "confirm":
        if text == "CONFIRM_ORDER": session["stage"] = "delivery"; await send_delivery_options(sender)
        elif text == "ADD_MORE": session["stage"] = "menu"; await send_main_menu(sender, session["order"])
        elif text == "CANCEL_ORDER":
            customer_sessions[sender] = {"stage": "menu", "order": [], "delivery_type": "", "address": "", "payment": ""}
            await send_text_message(sender, "Order cancel. Dobara order ke liye *Hi* likhein!")
        else: await send_order_summary(sender, session["order"])
        return

    if stage == "delivery":
        if text == "DELIVERY": session["stage"] = "address"; session["delivery_type"] = "delivery"; await send_text_message(sender, "Apna address likhein:")
        elif text == "PICKUP": session["delivery_type"] = "pickup"; session["stage"] = "payment"; await send_payment_options(sender)
        else: await send_delivery_options(sender)
        return

    if stage == "address":
        session["address"] = text; session["stage"] = "payment"
        await send_text_message(sender, f"Address save: {text}")
        await send_payment_options(sender)
        return

    if stage == "payment":
        if text in ["CASH", "CARD"]:
            session["payment"] = "Cash" if text == "CASH" else "Card/Online"
            session["stage"] = "done"
            await send_order_confirmed(sender, session)
            customer_sessions[sender] = {"stage": "welcome", "order": [], "delivery_type": "", "address": "", "payment": ""}
        else: await send_payment_options(sender)
        return

    await send_main_menu(sender)

async def send_main_menu(sender: str, current_order: list = []):
    cart_text = ""
    if current_order:
        total = sum(i["price"] for i in current_order)
        items_text = ", ".join([i["name"] for i in current_order])
        cart_text = f"\n\nCart: {items_text}\nTotal: AED {total}"

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "Wild Restaurant"},
            "body": {"text": f"Aapka swagat hai! Kya khaana chahenge?{cart_text}"},
            "footer": {"text": "Apni category chunein"},
            "action": {
                "button": "Menu Dekhein",
                "sections": [{"title": "Categories", "rows": [
                    {"id": "CAT_BURGERS", "title": "Burgers", "description": "Classic, Zinger, BBQ - AED 25-35"},
                    {"id": "CAT_PIZZA", "title": "Pizza", "description": "Margherita, BBQ, Pepperoni - AED 40-55"},
                    {"id": "CAT_DRINKS", "title": "Drinks", "description": "Cola, Juice, Water - AED 5-15"},
                    {"id": "CAT_SIDES", "title": "Sides", "description": "Fries, Rings, Coleslaw - AED 12-18"},
                ]}]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Main menu sent: {(await r.json()).get('messages', 'err')}")

async def send_category_menu(sender: str, category: str):
    items = MENU[category]
    rows = [{"id": f"ITEM_{k}", "title": v["name"], "description": f"AED {v['price']}"} for k, v in items.items()]
    emojis = {"Burgers": "Burgers", "Pizza": "Pizza", "Drinks": "Drinks", "Sides": "Sides"}
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": category},
            "body": {"text": f"{category} mein se kya lena chahenge?"},
            "footer": {"text": "Price AED mein"},
            "action": {"button": f"{category} Dekhein", "sections": [{"title": category, "rows": rows}]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Category menu sent: {category}")

async def send_item_added(sender: str, item: dict, order: list):
    total = sum(i["price"] for i in order)
    order_text = "\n".join([f"- {i['name']}: AED {i['price']}" for i in order])
    header_text = f"{item['name']} Add Ho Gaya!" if item else "Cart Update"
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": header_text},
            "body": {"text": f"Cart:\n{order_text}\n\nTotal: AED {total}\n\nAur add karna hai?"},
            "footer": {"text": "Wild Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": "Aur Add Karein"}},
                {"type": "reply", "reply": {"id": "CHECKOUT", "title": "Order Confirm"}},
                {"type": "reply", "reply": {"id": "REMOVE_LAST", "title": "Last Item Hatao"}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Item added msg sent")

async def send_add_more_btns(sender: str, order: list):
    total = sum(i["price"] for i in order)
    order_text = "\n".join([f"- {i['name']}: AED {i['price']}" for i in order])
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": f"Cart:\n{order_text}\n\nTotal: AED {total}"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": "Aur Add Karein"}},
                {"type": "reply", "reply": {"id": "CHECKOUT", "title": "Order Confirm"}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Add more btns sent")

async def send_order_summary(sender: str, order: list):
    total = sum(i["price"] for i in order)
    order_text = "\n".join([f"- {i['name']}: AED {i['price']}" for i in order])
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "Order Summary"},
            "body": {"text": f"Aapka Order:\n\n{order_text}\n\nTotal: AED {total}\n\nConfirm karna hai?"},
            "footer": {"text": "Wild Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "CONFIRM_ORDER", "title": "Haan, Confirm!"}},
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": "Aur Add Karein"}},
                {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": "Cancel"}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Order summary sent")

async def send_delivery_options(sender: str):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "Delivery ya Pickup?"},
            "body": {"text": "Kaise lena chahenge apna order?"},
            "footer": {"text": "Wild Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "DELIVERY", "title": "Home Delivery"}},
                {"type": "reply", "reply": {"id": "PICKUP", "title": "Khud Pickup"}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Delivery options sent")

async def send_payment_options(sender: str):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "Payment Method"},
            "body": {"text": "Aap kaise payment karenge?"},
            "footer": {"text": "Wild Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "CASH", "title": "Cash on Delivery"}},
                {"type": "reply", "reply": {"id": "CARD", "title": "Card/Online"}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            print(f"Payment options sent")

async def send_order_confirmed(sender: str, session_data: dict):
    import random
    order = session_data.get("order", [])
    total = sum(i["price"] for i in order)
    order_text = "\n".join([f"- {i['name']}: AED {i['price']}" for i in order])
    delivery_type = session_data.get("delivery_type", "pickup")
    address = session_data.get("address", "Restaurant Pickup")
    payment = session_data.get("payment", "Cash")
    order_id = random.randint(1000, 9999)
    eta = "30-45 min" if delivery_type == "delivery" else "15-20 min"
    msg = f"""Order Confirm! #{order_id}

{order_text}

Total: AED {total}
{'Delivery: ' + address if delivery_type == 'delivery' else 'Pickup: Restaurant se'}
Payment: {payment}
ETA: {eta}

Shukriya! Dobara order ke liye Hi likhein."""
    await send_text_message(sender, msg)

async def send_text_message(to: str, message: str):
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
    print(f"Twilio SMS: {form.get('Body')} from {form.get('From')}")
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")