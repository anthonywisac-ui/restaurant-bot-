import stripe
from config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from db import saved_orders
from whatsapp_handlers import send_text_message
import time

stripe.api_key = STRIPE_SECRET_KEY

async def create_stripe_checkout_session(order_id: str, amount: float):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"Order {order_id}"},
                    "unit_amount": int(amount * 100),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="https://restaurant-bot-production-a133.up.railway.app/success",  # replace with your actual domain
            cancel_url="https://restaurant-bot-production-a133.up.railway.app/cancel",
            metadata={"order_id": order_id},
            client_reference_id=order_id
        )
        return session.url
    except Exception as e:
        print(f"Stripe session creation failed: {e}")
        return None

async def handle_stripe_webhook(payload, sig_header):
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print(f"Webhook signature verification failed: {e}")
        return {"status": "error", "message": str(e)}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")
        if order_id and order_id in saved_orders:
            sender = saved_orders[order_id]["sender"]
            await send_text_message(sender, "✅ Payment received!\nOrder confirmed 🎉")
            # Optionally update sheet here as well
        else:
            print(f"Order {order_id} not found in saved_orders")
    return {"status": "ok"}
