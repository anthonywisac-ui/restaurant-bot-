import os
import time
import random
import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse
import uvicorn
import aiohttp
import re
import traceback

from .config import VERIFY_TOKEN, WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, STRIPE_SECRET_KEY
from .db import customer_sessions, saved_orders
from .flow import handle_flow, new_session
from .stripe_utils import handle_stripe_webhook
from .whatsapp_handlers import send_language_selection, send_text_message

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI()

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
            msg_type = message.get("type", "")
            if msg_type == "text":
                text = message["text"]["body"].strip()
                print(f"MSG: {text} from {sender}")
                # QR code scan detection
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

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    data = await request.json()
    order_id = data["order_id"]
    amount = data["amount"]
    # This endpoint might be used by the frontend; but we already have stripe_utils.
    # For simplicity, keep it or remove.
    return {"url": "https://example.com"}

@app.get("/success")
async def payment_success():
    return HTMLResponse("<h1>✅ Payment successful! Your order has been confirmed.</h1><p>You will receive a WhatsApp confirmation shortly.</p>")

@app.get("/cancel")
async def payment_cancel():
    return HTMLResponse("<h1>❌ Payment cancelled</h1><p>You can try again from the WhatsApp bot.</p>")

@app.post("/manager-update")
async def manager_update(request: Request):
    # copy from your original
    pass

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

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)