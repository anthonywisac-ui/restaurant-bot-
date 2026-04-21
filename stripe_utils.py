import stripe
import time
from config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from db import saved_orders
from whatsapp_handlers import send_text_message, send_order_confirmed, send_manager_action_list
from flow import save_profile, add_to_order_history, save_to_sheet
from utils import get_order_total, get_delivery_fee, get_order_text
from config import LANG_NAMES

stripe.api_key = STRIPE_SECRET_KEY

async def create_stripe_checkout_session(order_id: str, amount: float):
    """Create Stripe Checkout session and return the URL."""
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
            success_url="https://restaurant-bot-production-a133.up.railway.app/success",
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
        checkout_session = event["data"]["object"]
        order_id = checkout_session.get("metadata", {}).get("order_id")

        if not order_id or order_id not in saved_orders:
            print(f"Order {order_id} not found in saved_orders")
            return {"status": "ignored"}

        # Retrieve the saved customer session
        order_data = saved_orders[order_id]
        session_data = order_data.get("session")
        sender = order_data["sender"]

        if not session_data:
            print(f"No session data for order {order_id}")
            return {"status": "error"}

        # --- 1. Send FULL order confirmation to customer ---
        lang = session_data.get("lang", "en")
        await send_order_confirmed(sender, session_data, lang)

        # --- 2. Save order history and profile ---
        save_profile(sender, session_data)
        add_to_order_history(sender, order_id, session_data["order"])

        # --- 3. Notify manager with full order details ---
        await notify_manager_via_webhook(sender, session_data, order_id)

        # --- 4. Save to Google Sheet ---
        await save_to_sheet(sender, session_data, order_id)

        # --- 5. Update order status ---
        saved_orders[order_id]["payment_status"] = "paid"

        print(f"Order {order_id} fully confirmed and manager notified")

    return {"status": "ok"}

async def notify_manager_via_webhook(customer_number, session, order_id):
    """Replicate the manager notification logic from flow.py"""
    from config import MANAGER_NUMBER

    order = session.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = get_delivery_fee(total, session.get("delivery_type"))
    grand_total = total + tax + delivery_charge
    order_text = get_order_text(order)
    lang_name = LANG_NAMES.get(session.get("lang", "en"), "English")

    # Determine location line based on order type
    delivery_type = session.get("delivery_type")
    if delivery_type == "delivery":
        location_line = f"📍 Delivery: {session.get('address', '')}"
    elif delivery_type == "pickup":
        location_line = "🏪 Pickup"
    elif delivery_type == "dine_in":
        location_line = f"🍽️ Dine-in Table {session.get('table_number', '?')}"
    else:
        location_line = "📍 Not specified"

    eta_line = "30-45 mins" if delivery_type == "delivery" else "15-20 mins"

    body_text = (
        f"🔔 *NEW ORDER #{order_id}* (PAID)\n\n"
        f"👤 {session.get('name', 'N/A')}\n"
        f"📱 +{customer_number}\n"
        f"🌐 {lang_name}\n\n"
        f"{order_text}\n\n"
        f"Subtotal: ${total:.2f}\n"
        f"Tax: ${tax:.2f}\n"
        f"Delivery: ${delivery_charge:.2f}\n"
        f"*Total: ${grand_total:.2f}*\n\n"
        f"{location_line}\n"
        f"💳 Card (Stripe)\n"
        f"⏱️ ETA: {eta_line}"
    )

    await send_manager_action_list(
        order_id=order_id,
        customer_number=customer_number,
        header_text=f"🔔 New Order #{order_id} (PAID)",
        body_text=body_text,
        footer_text="Tap to update customer"
    )