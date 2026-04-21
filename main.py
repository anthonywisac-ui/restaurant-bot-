import os
import re
import time
import random
import traceback
import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse
import uvicorn
import aiohttp

# Import all modules
from config import VERIFY_TOKEN, WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, STRIPE_SECRET_KEY, MANAGER_NUMBER
from db import customer_sessions, saved_orders, customer_profiles
from flow import handle_flow, new_session, get_session, save_profile, add_to_order_history
from whatsapp_handlers import send_language_selection, send_text_message, send_cart_view
from stripe_utils import handle_stripe_webhook
from menu_data import MENU, reload_menu
from strings import reload_strings
from session import SharedSession

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI()

# ==================== WEBHOOKS ====================
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Forbidden", status_code=403)

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            sender = message["from"]

            # Ignore messages from the manager number
            if sender == MANAGER_NUMBER:
                print(f"Ignoring message from manager number {sender}")
                return {"status": "ok"}

            msg_type = message.get("type", "")
            if msg_type == "text":
                text = message["text"]["body"].strip()
                print(f"MSG: {text} from {sender}")
                # QR scan detection
                table_match = re.search(r'table=(\d+)', text)
                if table_match:
                    table_num = int(table_match.group(1))
                    customer_sessions[sender] = new_session(sender, table_number=table_num)
                    session = customer_sessions[sender]
                    session["stage"] = "lang_select"
                    session["order_type"] = "dine_in"
                    await send_language_selection(sender)
                    return
                await handle_flow(sender, text)
            elif msg_type == "interactive":
                interactive = message["interactive"]
                if interactive["type"] == "button_reply":
                    btn_id = interactive["button_reply"]["id"]
                    await handle_flow(sender, btn_id, is_button=True)
                elif interactive["type"] == "list_reply":
                    list_id = interactive["list_reply"]["id"]
                    await handle_flow(sender, list_id, is_button=True)
    except Exception as e:
        print(f"Webhook error: {e}\n{traceback.format_exc()}")
    return {"status": "ok"}

@app.post("/stripe-webhook")
async def stripe_webhook_endpoint(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    return await handle_stripe_webhook(payload, sig_header)

# ==================== STRIPE CHECKOUT SESSION ====================
@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    data = await request.json()
    order_id = data["order_id"]
    amount = int(data["amount"] * 100)
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"Order {order_id}"},
                "unit_amount": amount,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url="https://restaurant-bot-production-a133.up.railway.app/success",
        cancel_url="https://restaurant-bot-production-a133.up.railway.app/cancel",
        metadata={"order_id": order_id}
    )
    return {"url": session.url}

# ==================== SUCCESS / CANCEL PAGES ====================
@app.get("/success")
async def payment_success():
    return HTMLResponse("<h1>✅ Payment successful! Your order has been confirmed.</h1><p>You will receive a WhatsApp confirmation shortly.</p>")

@app.get("/cancel")
async def payment_cancel():
    return HTMLResponse("<h1>❌ Payment cancelled</h1><p>You can try again from the WhatsApp bot.</p>")

# ==================== MANAGER UPDATE ====================
@app.post("/manager-update")
async def manager_update(request: Request):
    import re
    from db import manager_pending, saved_orders
    from whatsapp_handlers import send_whatsapp_to_number
    from config import MANAGER_NUMBER

    data = await request.json()
    order_id_str = str(data.get("order_id", ""))
    status = data.get("status", "").upper()
    print(f"Manager update: Order #{order_id_str} -> {status}")

    try:
        order_id = int(order_id_str)
        customer_number = manager_pending.get(order_id)
        if not customer_number:
            print(f"No customer for order #{order_id}")
            return {"status": "not_found"}

        order_data = saved_orders.get(order_id, {})
        customer_name = order_data.get("customer_name", "Customer")
        delivery_type = order_data.get("delivery_type", "pickup")

        if "READY" in status and "DELIVERY" not in status:
            if delivery_type == "pickup":
                msg = f"🎉 Great news, {customer_name}! Your order #{order_id} is *READY for pickup!* Please come collect it."
            else:
                msg = f"🚚 Great news, {customer_name}! Your order #{order_id} is ready and *OUT FOR DELIVERY*. Should arrive in 15-20 minutes!"
        elif "OUT FOR DELIVERY" in status or "ON THE WAY" in status:
            msg = f"🚚 Hey {customer_name}, your order #{order_id} is *on the way!* Should arrive in 15-20 minutes!"
        elif "DELAYED" in status:
            delay_match = re.search(r'DELAYED\s*(\d+)', status)
            delay_time = delay_match.group(1) + " minutes" if delay_match else "a little longer"
            msg = f"⏱️ Hi {customer_name}, your order #{order_id} will take *{delay_time}* more than expected. Sorry for the wait! 🙏"
        elif "CANCELLED" in status:
            msg = f"❌ Hi {customer_name}, unfortunately order #{order_id} has been *cancelled*. Please contact us for a refund."
        else:
            msg = f"📢 Update on your order #{order_id}: {status}"

        # Send to customer
        await send_whatsapp_to_number(str(customer_number), msg)
        print(f"Customer {customer_number} updated for order #{order_id}")

        # Confirm to manager
        status_label = status
        if "READY" in status and "DELIVERY" not in status:
            status_label = "READY"
        elif "OUT FOR DELIVERY" in status:
            status_label = "OUT FOR DELIVERY"
        elif "DELAYED" in status:
            m = re.search(r'DELAYED\s*(\d+)', status)
            status_label = f"DELAYED {m.group(1)} min" if m else "DELAYED"
        elif "CANCELLED" in status:
            status_label = "CANCELLED"
        confirm_msg = f"✅ Order #{order_id} marked as *{status_label}*\n\nCustomer {customer_name} has been notified."
        await send_whatsapp_to_number(MANAGER_NUMBER, confirm_msg)

        return {"status": "ok"}
    except Exception as e:
        print(f"Manager update error: {e}")
        return {"status": "error"}

# ==================== TWILIO (optional) ====================
@app.post("/twilio-call")
async def twilio_call(request: Request):
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">Welcome to Wild Bites. Please WhatsApp us to order. Thank you!</Say>
</Response>"""
    return HTMLResponse(content=twiml, media_type="application/xml")

@app.post("/twilio-sms")
async def twilio_sms(request: Request):
    form = await request.form()
    print(f"SMS: {form.get('Body')} from {form.get('From')}")
    return {"status": "ok"}

# ==================== ADMIN RELOAD ====================
@app.post("/admin/reload")
async def admin_reload(secret: str):
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "change_this_in_railway")
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    reload_menu()
    reload_strings()
    return {"status": "ok", "message": "Menu and strings reloaded"}

# ==================== RUN ====================


@app.on_event("shutdown")
async def shutdown_event():
    await SharedSession.close_session()
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)